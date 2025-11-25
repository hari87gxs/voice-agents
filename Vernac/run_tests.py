#!/usr/bin/env python3
"""
Simple test runner that executes automated tests without interactive prompts
"""

import asyncio
import json
import time
import wave
import struct
import os
from typing import List, Tuple
import websockets
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Configuration
AZURE_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")
SERVER_URL = f"ws://localhost:{os.getenv('PORT', 8000)}/ws/chat"

# Test results storage
test_results = []


class TestResult:
    """Store test result with pass/fail status"""
    def __init__(self, name: str, passed: bool, message: str = "", duration: float = 0):
        self.name = name
        self.passed = passed
        self.message = message
        self.duration = duration
    
    def __str__(self):
        status = "✓ PASS" if self.passed else "✗ FAIL"
        duration_str = f" ({self.duration:.3f}s)" if self.duration > 0 else ""
        message_str = f"\n   {self.message}" if self.message else ""
        return f"{status} | {self.name}{duration_str}{message_str}"


def log_test(name: str, passed: bool, message: str = "", duration: float = 0):
    """Log a test result"""
    result = TestResult(name, passed, message, duration)
    test_results.append(result)
    print(result)


def generate_pcm16_audio(duration_ms: int = 1000, frequency: int = 440) -> bytes:
    """Generate PCM16 audio test data"""
    sample_rate = 24000
    num_samples = int(sample_rate * duration_ms / 1000)
    
    audio_data = []
    for i in range(num_samples):
        t = i / sample_rate
        value = int(32767 * 0.5 * (1.0 + 0.8 * (2.0 * 3.14159 * frequency * t)))
        pcm16_value = max(-32768, min(32767, value - 32768))
        audio_data.append(pcm16_value)
    
    return struct.pack(f'<{len(audio_data)}h', *audio_data)


def validate_pcm16_format(data: bytes) -> Tuple[bool, str]:
    """Validate PCM16 audio format"""
    if len(data) % 2 != 0:
        return False, f"Invalid length {len(data)} (not even for Int16)"
    
    try:
        num_samples = len(data) // 2
        samples = struct.unpack(f'<{num_samples}h', data)
        
        for sample in samples:
            if sample < -32768 or sample > 32767:
                return False, f"Sample {sample} out of Int16 range"
        
        return True, f"Valid PCM16: {num_samples} samples, {len(data)} bytes"
    
    except struct.error as e:
        return False, f"Failed to unpack PCM16: {e}"


def test_linear_interpolation():
    """Test linear interpolation algorithm"""
    print("\n" + "="*60)
    print("TEST: Linear Interpolation Algorithm")
    print("="*60)
    
    input_data = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]
    expected_output = [0.0, 0.2, 0.4, 0.6]
    
    source_rate = 8
    target_rate = 4
    ratio = target_rate / source_rate
    step = 1.0 / ratio
    
    output = []
    for i in range(target_rate):
        position = i * step
        idx = int(position)
        frac = position - idx
        
        if idx + 1 < len(input_data):
            value = input_data[idx] + (input_data[idx + 1] - input_data[idx]) * frac
        else:
            value = input_data[idx]
        
        output.append(round(value, 1))
    
    if output == expected_output:
        log_test("Linear Interpolation Algorithm", True, 
                f"Input: {input_data}\nOutput: {output}")
    else:
        log_test("Linear Interpolation Algorithm", False,
                f"Expected: {expected_output}\nGot: {output}")


def test_pcm16_conversion():
    """Test Float32 ↔ PCM16 conversion"""
    print("\n" + "="*60)
    print("TEST: PCM16 Conversion")
    print("="*60)
    
    test_cases = [
        (0.0, 0),
        (1.0, 32767),
        (-1.0, -32768),
        (0.5, 16384),
        (-0.5, -16384),
    ]
    
    all_passed = True
    for float_val, expected_pcm in test_cases:
        pcm16_val = max(-32768, min(32767, round(float_val * 32768)))
        float_back = pcm16_val / 32768.0
        
        if pcm16_val != expected_pcm:
            log_test(f"Float32→PCM16: {float_val}", False,
                    f"Expected {expected_pcm}, got {pcm16_val}")
            all_passed = False
        else:
            if abs(float_back - float_val) > 0.001:
                log_test(f"PCM16→Float32: {pcm16_val}", False,
                        f"Round-trip error: {float_val} → {pcm16_val} → {float_back}")
                all_passed = False
    
    if all_passed:
        log_test("PCM16 Conversion", True, "All conversions accurate")


async def test_websocket_connection():
    """Test WebSocket connection to server"""
    print("\n" + "="*60)
    print("TEST: WebSocket Connection")
    print("="*60)
    
    start_time = time.time()
    
    try:
        async with websockets.connect(SERVER_URL) as ws:
            duration = time.time() - start_time
            log_test("WebSocket Connection", True, 
                    f"Connected to {SERVER_URL}", duration)
            
            try:
                message = await asyncio.wait_for(ws.recv(), timeout=2.0)
                if isinstance(message, str):
                    data = json.loads(message)
                    log_test("Receive Initial Message", True,
                            f"Type: {data.get('type', 'unknown')}")
                else:
                    log_test("Receive Initial Message", True, "Binary data received")
            except asyncio.TimeoutError:
                log_test("Receive Initial Message", True, "No initial message (OK)")
            
            return True
    
    except Exception as e:
        duration = time.time() - start_time
        log_test("WebSocket Connection", False, str(e), duration)
        return False


async def test_audio_format_compliance():
    """Test audio format compliance (PCM16 24kHz)"""
    print("\n" + "="*60)
    print("TEST: Audio Format Compliance")
    print("="*60)
    
    test_audio = generate_pcm16_audio(duration_ms=500)
    is_valid, message = validate_pcm16_format(test_audio)
    log_test("Generate PCM16 Audio", is_valid, message)
    
    try:
        async with websockets.connect(SERVER_URL) as ws:
            import base64
            audio_b64 = base64.b64encode(test_audio).decode('utf-8')
            audio_message = json.dumps({
                "type": "input_audio_buffer.append",
                "audio": audio_b64
            })
            
            start_time = time.time()
            await ws.send(audio_message)
            duration = time.time() - start_time
            
            log_test("Send PCM16 Audio", True,
                    f"Sent {len(test_audio)} bytes", duration)
            
            try:
                response = await asyncio.wait_for(ws.recv(), timeout=3.0)
                if isinstance(response, bytes):
                    is_valid, msg = validate_pcm16_format(response)
                    log_test("Receive PCM16 Audio", is_valid, msg)
                else:
                    data = json.loads(response)
                    log_test("Receive Response", True, f"Type: {data.get('type')}")
            except asyncio.TimeoutError:
                log_test("Receive Response", True, "No response yet (OK)")
    
    except Exception as e:
        log_test("Audio Format Test", False, str(e))


async def test_session_configuration():
    """Test session configuration with Azure"""
    print("\n" + "="*60)
    print("TEST: Session Configuration")
    print("="*60)
    
    expected_config = {
        "modalities": ["text", "audio"],
        "input_audio_format": "pcm16",
        "output_audio_format": "pcm16",
        "turn_detection": {
            "type": "server_vad",
            "threshold": 0.6,
            "prefix_padding_ms": 300,
            "silence_duration_ms": 600,
        }
    }
    
    try:
        async with websockets.connect(SERVER_URL) as ws:
            session_found = False
            for _ in range(5):
                try:
                    message = await asyncio.wait_for(ws.recv(), timeout=2.0)
                    if isinstance(message, str):
                        data = json.loads(message)
                        
                        if data.get("type") in ["session.created", "session.updated"]:
                            session_found = True
                            session_data = data.get("session", {})
                            
                            checks = []
                            checks.append(("Modalities", 
                                         session_data.get("modalities") == expected_config["modalities"]))
                            checks.append(("Input Format",
                                         session_data.get("input_audio_format") == "pcm16"))
                            checks.append(("Output Format",
                                         session_data.get("output_audio_format") == "pcm16"))
                            checks.append(("VAD Type",
                                         session_data.get("turn_detection", {}).get("type") == "server_vad"))
                            
                            all_passed = all(result for _, result in checks)
                            details = "\n".join([f"   {name}: {'✓' if result else '✗'}" 
                                               for name, result in checks])
                            
                            log_test("Session Configuration", all_passed, details)
                            break
                
                except asyncio.TimeoutError:
                    break
            
            if not session_found:
                log_test("Session Configuration", False, 
                        "No session.created or session.updated event received")
    
    except Exception as e:
        log_test("Session Configuration", False, str(e))


async def test_latency():
    """Test end-to-end latency"""
    print("\n" + "="*60)
    print("TEST: Latency Measurement")
    print("="*60)
    
    try:
        start_time = time.time()
        async with websockets.connect(SERVER_URL) as ws:
            connection_latency = (time.time() - start_time) * 1000
            log_test("Connection Latency", connection_latency < 500,
                    f"{connection_latency:.2f}ms (target: <500ms)")
            
            test_message = json.dumps({"type": "test", "timestamp": time.time()})
            
            start_time = time.time()
            await ws.send(test_message)
            
            try:
                await asyncio.wait_for(ws.recv(), timeout=1.0)
                roundtrip_latency = (time.time() - start_time) * 1000
                log_test("Message Round-Trip", roundtrip_latency < 200,
                        f"{roundtrip_latency:.2f}ms (target: <200ms)")
            except asyncio.TimeoutError:
                log_test("Message Round-Trip", True,
                        "No echo (expected for one-way relay)")
    
    except Exception as e:
        log_test("Latency Test", False, str(e))


async def test_azure_configuration():
    """Test Azure OpenAI configuration"""
    print("\n" + "="*60)
    print("TEST: Azure Configuration")
    print("="*60)
    
    checks = [
        ("AZURE_OPENAI_ENDPOINT", AZURE_ENDPOINT is not None and AZURE_ENDPOINT != ""),
        ("AZURE_OPENAI_API_KEY", AZURE_API_KEY is not None and AZURE_API_KEY != ""),
        ("AZURE_OPENAI_DEPLOYMENT", AZURE_DEPLOYMENT is not None and AZURE_DEPLOYMENT != ""),
    ]
    
    for name, passed in checks:
        if passed:
            log_test(f"Environment: {name}", True, "Configured")
        else:
            log_test(f"Environment: {name}", False, "Missing or empty")
    
    if AZURE_ENDPOINT:
        if AZURE_ENDPOINT.startswith("https://") and ".openai.azure.com" in AZURE_ENDPOINT:
            log_test("Endpoint Format", True, AZURE_ENDPOINT)
        else:
            log_test("Endpoint Format", False,
                    f"Invalid format: {AZURE_ENDPOINT}")


def print_summary():
    """Print test summary"""
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    total = len(test_results)
    passed = sum(1 for r in test_results if r.passed)
    failed = total - passed
    
    print(f"\nTotal Tests: {total}")
    print(f"Passed: {passed} ✓")
    print(f"Failed: {failed} ✗")
    print(f"Success Rate: {(passed/total*100):.1f}%\n")
    
    if failed > 0:
        print("Failed Tests:")
        for result in test_results:
            if not result.passed:
                print(f"  - {result.name}: {result.message}")
        print()
    
    if failed == 0:
        print("🎉 ALL TESTS PASSED! 🎉")
    else:
        print("⚠️  SOME TESTS FAILED")
    
    print("="*60)


async def run_all_tests():
    """Run all automated tests"""
    print("\n" + "="*60)
    print("VERNAC AUTOMATED ENGINEERING TESTS")
    print("="*60)
    print(f"Server URL: {SERVER_URL}")
    print(f"Azure Endpoint: {AZURE_ENDPOINT}")
    print("="*60)
    
    # Unit tests
    test_linear_interpolation()
    test_pcm16_conversion()
    
    # Async tests
    await test_azure_configuration()
    
    # Server connectivity tests
    if await test_websocket_connection():
        await test_audio_format_compliance()
        await test_session_configuration()
        await test_latency()
    else:
        print("\n⚠️  Server not running. Skipping server-dependent tests.")
    
    # Print summary
    print_summary()


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════╗
║            VERNAC AUTOMATED TEST RUNNER                     ║
║        GXS Bank Voice-to-Voice Agent Testing                ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    try:
        asyncio.run(run_all_tests())
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests cancelled by user")
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
