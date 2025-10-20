from machine import mem32

def deepsleep():
    # mem32[0x4002752C]
    # mem32[0x40027500] = 1 #seemed necessary for seeed xiao nrf, This de-activates the usb device. Decomment if
    mem32[0x40000500] = 1
    return False # Will not return

def get_wake_pins():
    l0 = mem32[0x50000520]
    l1 = mem32[0x50000820]
    pos = [i for i in range(32) if l0 & (1 << i)]
    pos.extend(i + 32 for i in range(16) if l1 & (1 << i))
    mem32[0x50000520] = l0 # This will release the latches
    mem32[0x50000820] = l1
    return pos

def set_sense_pin(p, wake_on_hi=True, twitch = False): # Sorry, I know, not very human-readable
    if p < 32:
        d = 0x50000524
        r = 0x50000700 + p << 2
        mem32[0x50000520] = 1 << p
    else:
        d = 0x50000824
        r = 0x50000a00 + (p - 32) << 2
        mem32[0x50000820] = 1 << (p - 32)
    mem32[d] = 0
    mem32[r] = 0x20004 if wake_on_hi else 0x3000c if not twitch else 0x2000c

class SleepMemory:
    def __init__(self, ram, sector):
        self.adr = 0x2000000 + (ram + sector) << 12 if ram < 7 else 0x2001000 + sector << 15
        self.ram = ram
        self.sector = sector
        self.sz = 0
        self.mx = 0x1000 if ram < 7 else 0x8000

    def __getitem__(self, key):
        if isinstance(key, slice) and key.start is None and key.stop is None and key.step is None:
            return self.value
        raise TypeError('Only full-slice access ([:]) is supported')

    def __setitem__(self, key, val):
        if isinstance(key, slice) and key.start is None and key.stop is None and key.step is None:
            self.value = val
            return
        raise TypeError('Only full-slice assignment ([:]) is supported')

    @property
    def value(self):
        b = bytearray(b''.join(mem32[self.adr + i << 2].to_bytes(4, 'little') for i in range(self.sz)))
        self.sz = int.from_bytes(b[:2], "little")
        return b[2:self.sz << 2 - 2]

    @value.setter
    def value(self, value):
        if not isinstance(value, (bytes, bytearray)):
            raise TypeError ('Value must be bytes or bytearray')
        # compute number of 4-byte words and store in self.sz (first 16 bits)
        self.sz = (len(value)+ 2 + 3) >> 2
        for chnk in range(self.sz):
            if chnk == 0:
                v = int.from_bytes(value[:2], 'little') + (self.sz << 16)
                st = 0
            else:
                st =  2 + (chnk - 1) << 2
                chunk = value[st:st + 4]
                if len(chunk) < 4:
                    chunk = chunk + b'\x00' * (4 - len(chunk))
                v = int.from_bytes(chunk, 'little')
            mem32[self.adr + st<<2] = v

    def set_retain(self):
        adr = 0x40000900 + self.ram << 4
        sct_on = 1 << (16 + self.sector)
        mem32[adr] |= sct_on

def rtcmem(b = None):
    # Only 2 bytes available
    if b and isinstance(b, (bytearray, bytes))  and len(b) <= 2:
        mem32[0x4000051C] = b[0]
        if len(b) == 2:
            mem32[0x40000520] = b[1]
    elif b:
        raise ValueError('RTC mem write must be 1 or 2 bytes')
    else:
        return bytes([mem32[0x4000051C] & 0xFF, mem32[0x40000520] & 0xFF])

def read_uicr(n):
    if 0 > n > 31:
        raise ValueError('UICR registers are only 0 to 31')
    adr = 0x10001000 + n << 2
    return mem32[adr].to_bytes(4, 'little')

def burnin_uicr(n, val):
    # You can erase it, but you need to erase the whole chip with a programmer
    if 0 > n > 31:
        raise ValueError('UICR registers are only 0 to 31')
    adr = 0x10001000 + n << 2
    if mem32[adr] == 4294967295 and isinstance(val, (bytes, bytearray)) and len(val) == 4: # If that register is virgin
        mem32[adr] = int.from_bytes(val, 'little')
    else:
        raise OSError('Register not empty, can only write once')
