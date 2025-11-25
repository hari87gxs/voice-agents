/**
 * Vernac - PCM Audio Processor (AudioWorklet)
 * 
 * This AudioWorklet processor performs high-quality audio resampling from the browser's
 * native sample rate (typically 48kHz) to the target rate of 24kHz required by Azure OpenAI.
 * 
 * KEY FEATURE: Linear Interpolation Resampling
 * ============================================
 * Unlike simple decimation (which just drops samples and causes aliasing), this processor
 * uses LINEAR INTERPOLATION to calculate intermediate sample values.
 * 
 * Mathematical Explanation:
 * ------------------------
 * When downsampling from 48kHz to 24kHz (ratio = 0.5), we need to generate samples at
 * positions that fall between existing samples in the source audio.
 * 
 * For example, if we want a sample at position 2.3:
 * - We take sample[2] and sample[3]
 * - We interpolate: value = s[2] + (s[3] - s[2]) * 0.3
 * 
 * Formula: val = s[idx] + (s[idx+1] - s[idx]) * (pos - idx)
 *          where pos is the fractional position in source audio
 * 
 * This produces much better audio quality by smoothly transitioning between samples
 * rather than creating harsh discontinuities.
 * 
 * Float32 to PCM16 Conversion:
 * ----------------------------
 * Browser audio is Float32 in range [-1.0, 1.0]
 * Azure expects PCM16 (Int16) in range [-32768, 32767]
 * 
 * Conversion: pcm16_value = Math.max(-32768, Math.min(32767, Math.round(float32_value * 32768)))
 */

class PCMProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    
    // Target sample rate for Azure OpenAI
    this.targetSampleRate = 24000;
    
    // Source sample rate (will be set from actual input)
    this.sourceSampleRate = 48000; // Default, updated on first process
    
    // Resampling ratio (target / source)
    this.resampleRatio = this.targetSampleRate / this.sourceSampleRate;
    
    // Position tracker for reading source samples
    // This maintains fractional position as we generate output samples
    this.sourcePosition = 0;
    
    // Buffer to accumulate samples before sending
    this.outputBuffer = [];
    
    // Send chunks of this size (in samples) - about 240ms at 24kHz
    this.chunkSize = 4800;
    
    // Flag to track if sample rate has been initialized
    this.initialized = false;
    
    // Port for sending processed audio to main thread
    this.port.onmessage = (event) => {
      if (event.data.type === 'configure') {
        this.sourceSampleRate = event.data.sourceSampleRate || 48000;
        this.resampleRatio = this.targetSampleRate / this.sourceSampleRate;
        this.initialized = true;
      }
    };
  }
  
  /**
   * Main processing function called for each audio buffer (128 samples)
   * @param {Float32Array[][]} inputs - Input audio channels
   * @param {Float32Array[][]} outputs - Output audio channels (unused, we send via port)
   * @param {Object} parameters - Audio parameters
   * @returns {boolean} - true to keep processor alive
   */
  process(inputs, outputs, parameters) {
    const input = inputs[0];
    
    // If no input or no channels, skip processing
    if (!input || input.length === 0) {
      return true;
    }
    
    // Initialize sample rate from actual input on first process
    if (!this.initialized && sampleRate) {
      this.sourceSampleRate = sampleRate;
      this.resampleRatio = this.targetSampleRate / this.sourceSampleRate;
      this.initialized = true;
    }
    
    // Get first channel (mono) - if stereo, we'll convert to mono
    const channel0 = input[0];
    const channel1 = input[1] || null;
    
    // Convert stereo to mono if needed (average the channels)
    let monoInput;
    if (channel1) {
      // Stereo to mono conversion
      monoInput = new Float32Array(channel0.length);
      for (let i = 0; i < channel0.length; i++) {
        monoInput[i] = (channel0[i] + channel1[i]) / 2.0;
      }
    } else {
      // Already mono
      monoInput = channel0;
    }
    
    // Resample using linear interpolation
    const resampled = this.resampleWithLinearInterpolation(monoInput);
    
    // Convert Float32 to PCM16 (Int16)
    const pcm16 = this.floatToPCM16(resampled);
    
    // Add to output buffer
    this.outputBuffer.push(...pcm16);
    
    // Send chunks when buffer is large enough
    while (this.outputBuffer.length >= this.chunkSize) {
      const chunk = this.outputBuffer.splice(0, this.chunkSize);
      const int16Array = new Int16Array(chunk);
      
      // Send to main thread via port
      this.port.postMessage({
        type: 'audioData',
        data: int16Array.buffer
      }, [int16Array.buffer]); // Transfer ownership for zero-copy
    }
    
    return true; // Keep processor alive
  }
  
  /**
   * Resample audio using LINEAR INTERPOLATION
   * 
   * This is the CRITICAL DSP function that prevents audio artifacts.
   * 
   * Algorithm:
   * 1. Calculate how many output samples we need (inputLength * ratio)
   * 2. For each output sample, calculate its position in the input array
   * 3. Use linear interpolation between the two nearest input samples
   * 
   * Example with 48kHz → 24kHz (ratio = 0.5):
   * - Output sample 0 maps to input position 0
   * - Output sample 1 maps to input position 2
   * - Output sample 2 maps to input position 4
   * - etc.
   * 
   * Example with fractional positions:
   * - If output sample maps to input position 2.7:
   *   - Take sample[2] = s2 and sample[3] = s3
   *   - Interpolate: value = s2 + (s3 - s2) * 0.7
   * 
   * @param {Float32Array} input - Source audio samples (Float32)
   * @returns {Float32Array} - Resampled audio at target rate
   */
  resampleWithLinearInterpolation(input) {
    // Calculate number of output samples
    // For 48kHz → 24kHz with 128 input samples: 128 * 0.5 = 64 output samples
    const outputLength = Math.floor(input.length * this.resampleRatio);
    const output = new Float32Array(outputLength);
    
    // The step size in the input array for each output sample
    // For 48kHz → 24kHz: step = 1 / 0.5 = 2.0 (we skip every other sample, but interpolate)
    const step = 1.0 / this.resampleRatio;
    
    // Process each output sample
    for (let i = 0; i < outputLength; i++) {
      // Calculate position in input array
      // Position can be fractional (e.g., 2.3, 5.7, etc.)
      const position = this.sourcePosition + (i * step);
      
      // Get integer part (index of lower sample)
      const index = Math.floor(position);
      
      // Get fractional part (0.0 to 1.0) - this is the interpolation weight
      // If position = 2.3, then index = 2 and fraction = 0.3
      const fraction = position - index;
      
      // Boundary check: ensure we have a next sample for interpolation
      if (index + 1 < input.length) {
        // LINEAR INTERPOLATION FORMULA
        // ============================
        // val = s[idx] + (s[idx+1] - s[idx]) * fraction
        // 
        // This calculates a weighted average:
        // - When fraction = 0.0: val = s[idx] (use lower sample entirely)
        // - When fraction = 0.5: val = average of both samples
        // - When fraction = 1.0: val = s[idx+1] (use upper sample entirely)
        // - When fraction = 0.3: val is 70% s[idx] + 30% s[idx+1]
        
        const sample0 = input[index];       // Lower sample
        const sample1 = input[index + 1];   // Upper sample
        
        // Interpolate between the two samples
        output[i] = sample0 + (sample1 - sample0) * fraction;
        
      } else {
        // Edge case: we're at the last sample, no interpolation possible
        output[i] = input[index] || 0;
      }
    }
    
    // Update source position for next buffer
    // This maintains continuity between process() calls
    this.sourcePosition = (this.sourcePosition + (outputLength * step)) % input.length;
    
    return output;
  }
  
  /**
   * Convert Float32 audio samples to PCM16 (Int16)
   * 
   * Browser audio: Float32 in range [-1.0, 1.0]
   * Azure expects: Int16 in range [-32768, 32767]
   * 
   * Formula: pcm16 = clamp(round(float32 * 32768), -32768, 32767)
   * 
   * @param {Float32Array} floatSamples - Float32 audio samples
   * @returns {Array<number>} - Array of Int16 values
   */
  floatToPCM16(floatSamples) {
    const pcm16 = [];
    
    for (let i = 0; i < floatSamples.length; i++) {
      // Multiply by 32768 to scale from [-1.0, 1.0] to [-32768, 32768]
      let val = floatSamples[i] * 32768;
      
      // Clamp to Int16 range and round to integer
      // This prevents overflow and ensures valid PCM16 values
      val = Math.max(-32768, Math.min(32767, Math.round(val)));
      
      pcm16.push(val);
    }
    
    return pcm16;
  }
}

// Register the processor with the AudioWorklet system
// This makes it available to be loaded via audioWorklet.addModule()
registerProcessor('pcm-processor', PCMProcessor);
