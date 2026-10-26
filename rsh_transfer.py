"""Bounded XMODEM/YMODEM engines with fragmented reads and host-only progress."""
import binascii
from contextlib import nullcontext
from functools import wraps
from pathlib import Path
import shutil
import tempfile
import time

SOH, STX, EOT, ACK, NAK, CAN = 1, 2, 4, 6, 21, 24
RETRIES = 10


def _check(ser):
    service = getattr(ser, '_rsh_services', None)
    if service and service.cancelled.is_set():
        raise InterruptedError('Transfer cancelled from host.')


def read_exact(ser, count, timeout=10):
    deadline = time.monotonic() + timeout
    data = bytearray()
    while len(data) < count:
        _check(ser)
        block = ser.read(count - len(data))
        if block:
            data.extend(block)
        elif time.monotonic() >= deadline:
            raise TimeoutError('Timed out waiting for transfer data.')
        else:
            time.sleep(.01)
    return bytes(data)


def wait_for(ser, accepted, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = read_exact(ser, 1, max(.01, deadline - time.monotonic()))[0]
        if value == CAN:
            raise InterruptedError('Receiver cancelled the transfer.')
        if value in accepted:
            return value
    raise TimeoutError('Timed out waiting for acknowledgment.')


def packet(number, data, crc=True):
    checksum = binascii.crc_hqx(data, 0).to_bytes(2, 'big') if crc else bytes([sum(data) & 255])
    return bytes([STX if len(data) == 1024 else SOH, number & 255, 255 - (number & 255)]) + data + checksum


def progress(ser, direction, done, total, retries=0):
    elapsed = max(.001, time.monotonic() - getattr(ser, '_rsh_transfer_started', time.monotonic()))
    ser._rsh_transfer_progress = {'direction':direction, 'bytes':done, 'total':total, 'retries':retries,
                                  'elapsed_seconds':round(elapsed,1), 'bytes_per_second':round(done/elapsed,1)}
    service = getattr(ser, '_rsh_services', None)
    if service:
        service.progress = dict(ser._rsh_transfer_progress)


def protected(function):
    @wraps(function)
    def invoke(ser, *args, **kwargs):
        service = getattr(ser, '_rsh_services', None)
        with service.transfer() if service else nullcontext():
            try:
                ser._rsh_transfer_started = time.monotonic()
                return function(ser, *args, **kwargs)
            except (TimeoutError, InterruptedError, OSError, ValueError) as exc:
                ser.write(bytes([CAN, CAN]))
                raise
            finally:
                ser._rsh_transfer_progress = None
    return invoke


def send_packet(ser, data, direction, done, total):
    for retry in range(RETRIES):
        progress(ser, direction, done, total, retry)
        ser.write(data)
        try:
            response = wait_for(ser, (ACK, NAK))
            if response == ACK:
                return
        except TimeoutError:
            continue
    raise TimeoutError('Retry limit exceeded.')


@protected
def xsend(ser, filename):
    path = Path(filename)
    total = path.stat().st_size
    crc = wait_for(ser, (NAK, ord('C')), 20) == ord('C')
    number, done = 1, 0
    with path.open('rb') as source:
        for block in iter(lambda: source.read(128), b''):
            send_packet(ser, packet(number, block.ljust(128, b'\x1a'), crc), 'send', done, total)
            done += len(block); number = (number + 1) & 255
    send_packet(ser, bytes([EOT]), 'send', total, total)
    return total


@protected
def xreceive(ser, destination, exact_size=None):
    path = Path(destination)
    if path.exists():
        raise FileExistsError('Destination already exists.')
    if exact_size is not None and exact_size < 0:
        raise ValueError('Expected file size must be nonnegative.')
    temporary = tempfile.NamedTemporaryFile(prefix=path.name + '-', suffix='.part', dir=path.parent, delete=False)
    partial = Path(temporary.name)
    expected, done, errors, started = 1, 0, 0, False
    last_size = 128
    crc = True
    try:
        with temporary as output:
            while True:
                _check(ser)
                if not started:
                    ser.write(b'C' if crc else bytes([NAK]))
                try:
                    marker = read_exact(ser, 1, 3 if not started else 10)[0]
                except TimeoutError:
                    errors += 1
                    if errors >= RETRIES:
                        raise
                    if not started:
                        crc = errors < 3
                    else:
                        ser.write(bytes([NAK]))
                    continue
                if marker == CAN:
                    raise InterruptedError('Sender cancelled the transfer.')
                if marker == EOT:
                    if exact_size is not None:
                        if exact_size > done or done - exact_size >= last_size:
                            raise ValueError('Received size does not match expected file size.')
                        output.truncate(exact_size)
                    break
                if marker not in (SOH, STX):
                    errors += 1
                    if errors >= RETRIES:
                        raise ValueError('Too many invalid transfer headers.')
                    continue
                started = True
                length = 128 if marker == SOH else 1024
                try:
                    data = read_exact(ser, length + 2 + (2 if crc else 1))
                except TimeoutError:
                    errors += 1
                    if errors >= RETRIES:
                        raise
                    ser.write(bytes([NAK])); continue
                number, complement = data[:2]
                body, trailer = data[2:2+length], data[2+length:]
                valid = number + complement == 255 and (binascii.crc_hqx(body, 0).to_bytes(2,'big') == trailer if crc else (sum(body) & 255) == trailer[0])
                if not valid or number not in ((expected, (expected - 1) & 255) if done else (expected,)):
                    errors += 1
                    if errors >= RETRIES:
                        raise ValueError('Too many damaged or out-of-order blocks.')
                    ser.write(bytes([NAK])); continue
                if number == expected:
                    output.write(body); done += length; expected = (expected+1) & 255; last_size = length
                errors = 0
                progress(ser, 'receive', done, exact_size)
                ser.write(bytes([ACK]))
        with path.open('xb') as output, partial.open('rb') as source:
            shutil.copyfileobj(source, output)
        partial.unlink()
        ser.write(bytes([ACK]))
        return path.stat().st_size
    except BaseException:
        # Keep an explicitly named partial file for diagnosis; never trim binary data.
        raise


@protected
def ysend(ser, filename):
    path = Path(filename)
    total = path.stat().st_size
    header = path.name.encode('ascii') + b'\0' + str(total).encode('ascii') + b'\0'
    if len(header) > 128:
        raise ValueError('YMODEM filename/header is too long.')
    wait_for(ser, (ord('C'),), 20)
    send_packet(ser, packet(0, header.ljust(128, b'\0')), 'send', 0, total)
    wait_for(ser, (ord('C'),))
    number, done = 1, 0
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024), b''):
            send_packet(ser, packet(number, block.ljust(1024, b'\x1a')), 'send', done, total)
            number = (number + 1) & 255; done += len(block)
    for retry in range(RETRIES):
        ser.write(bytes([EOT]))
        try:
            if wait_for(ser, (NAK, ACK)) == ACK:
                break
        except TimeoutError:
            pass
    else:
        raise TimeoutError('YMODEM end-of-file acknowledgment timed out.')
    wait_for(ser, (ord('C'),))
    send_packet(ser, packet(0, bytes(128)), 'send', total, total)
    return total
