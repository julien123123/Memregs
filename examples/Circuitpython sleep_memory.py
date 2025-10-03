import alarm, memregs, time, board, digitalio, microcontroller, os

"""
This is an example on how you can manage sleep_memory in circuitpython with memregs. Out of the box, Circuitpython doesn't
include uctypes, so if you don't install the library, only memregs.Pack will work.
"""
sm = alarm.sleep_memory
led = digitalio.DigitalInOut(board.LED)
led.direction = digitalio.Direction.OUTPUT
led.value = True

# Items structure ('NAME', len, bin = False, format = 'B') The format is the same struct formats
values = memregs.Pack('values', sm, 0, ('REFRESH', 1), ('MAGIC', 4), ('FLAG', 1, True),
                        ('INIT_TIME', 1, False,'L'), ('READINGS', 5), span=16)

def pretend_sensor_readings_FIFO(ar):
    tmp = bytearray(ar.value[1:])
    tmp.append(os.urandom(1)[0])
    # Let's say this would be a sensor reading, so that your device remembers the last 5
    ar.value = tmp
    values.post_all()

time_alarm = alarm.time.TimeAlarm(monotonic_time=time.monotonic() + 2)

if values['MAGIC'] != b'CAFE':
    values['INIT_TIME'].value = time.time()
    values['MAGIC'] = b'CAFE'
    values.post_all()

print(f"sleep_memory: {sm[:32]}")
pretend_sensor_readings_FIFO(values['READINGS'])

st = ''
for b in values['READINGS'].value:
    st += '.'*(b//51+1)
    st += '\n'

print(f"\n[RANDOM GRAPH]\n{st}")
print(f'Number of times this file has run: {values['REFRESH'].value[0]} | First init time: {time.localtime(values['INIT_TIME'].value)}')
print(f'FLAG = {values['FLAG'].value}')
values['REFRESH'] += 1
values['FLAG'] = 1 if values['REFRESH'].value[0] >=5 else 0
values.post_all()

led.value = False
alarm.exit_and_deep_sleep_until_alarms(time_alarm) if not values['FLAG'].value else None