import machine, time, os, memregs

class RTCWrapper:
    # This wrapper makes micropython's implementation of the ESP-32's RTC memory compatible with memregs classes as you
    # need to use the memory() function to record and read from it. Circuitpython's version alarm.sleep_memory doesn't
    # need this wrapper.

    def __init__(self, sz):
        self._rtc = machine.RTC().memory
        self._sz = sz
        
        dt = self._rtc() or b""
        self._buf = bytearray(dt[:sz])
        self._buf.extend([0x00] * (sz - len(self._buf))) if len(self._buf) < sz else None
        self._rtc(self._buf)

    def __getitem__(self, key): return self._buf[key]
    def __setitem__(self, key, value):
        if isinstance(key, slice):
            stp = key.stop if key.stop is not None else self._sz
            maxl = stp - (key.start or 0)
            if len(value) > maxl:
                value = value[:maxl]
        self._buf[key] = value
        if len(self._buf) < self._sz:
            self._buf.extend([0x00]* (self._sz - len(self._buf)))
        elif len(self._buf) > self._sz:
            del self._buf[self._sz:]
        self._rtc(self._buf)
        
    def __len__(self): return self._sz
    def __repr__(self): return f"<FixedRTCBuffer size={self._sz} data={self._buf!r}>"

# Change this to your board's boot button if it's different.
boot = machine.Pin(9, machine.Pin.IN)

def flag_toggle(button):
    values.toggle('FLAG')
    values.post_all() # This will make micropython remember you pressed the button between reboots

    # If you wanted for wanted to be able to raise the flag when the device is in deepsleep as well, you could use this
    # pin as wake_on_ext and detect the wake_reason and raise the flag if it was wake_on_ext. This is useful if you have
    # a device running on batteries, and you want to use a button.

def pretend_sensor_readings_FIFO(ar):
    tmp = ar[1:]
    tmp.append(os.urandom(1)[0]) # Let's say this would be a sensor reading, so that your device remembers the last 5
    ar[:] = tmp

# That way, if you rename this file "main.py", you should be able to stop it from looping by pressing the boot button
boot.irq(flag_toggle, machine.Pin.IRQ_FALLING)

rtc = RTCWrapper(16)

# Items structure ('NAME', len, bin = False, format = 'UINT8') The format is the same as uctypes formats
values = memregs.Struct('values', rtc, 0, ('REFRESH', 1), ('MAGIC', 4, 'ARRAY'), ('FLAG', 1, True),
                        ('INIT_TIME', 1, 'UINT16'), ('READINGS', 5, 'ARRAY'), span=16)

if values['MAGIC'] != b'CAFE':
    values['INIT_TIME'] = time.time()
    values['MAGIC'] = b'CAFE'

print(rtc)
pretend_sensor_readings_FIFO(values['READINGS'])

st = ''
for b in values['READINGS']:
    st += '.'*(b//51+1)
    st += '\n'

print(f"\n[RANDOM GRAPH]\n{st}")
print(f'Number of times this file has run: {values['REFRESH']} | First init time: {time.localtime(values['INIT_TIME'])}')
print(f'FLAG = {values['FLAG']}')
values['REFRESH'] += 1
values.post_all()

time.sleep(1) # just to give you enough time to press the button

machine.deepsleep(1) if not values['FLAG'] else None

