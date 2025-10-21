# Nrf utils

This file makes some basics micropython functions available to the NRF52840 port (curently they are not implemented). I
tested all of them on both the NRF52840 Super Mini / Nice! Nano with the adafruit bootloader, and the Seeed Xiao Nrf52840.

## deepsleep()

Similar to machine.deepsleep() on other ports. This function puts the NRF52 in system off mode. The power consumption will
be very low, but in this mode, the RTC is completely shutdown.

>[!NOTE]
> When waking up from System off, or deepsleep, machine.reset_cause() will be `16`.

## get_wake_pins()

This returns the pins that woke up the NRF52 from sleep AND unlatches them.

## set_sense_pin(p, wake_on_hi=True, twitch = False)

- `p` pin number. If the pin you want to use is marked as 1.something, just add 32 to the number after the point to get it's
number

- `wake_on_hi` if `True`, configures the pin with a pulldown resistor and wakes up the device when high. If `False`, it will
turn on the internal pull up resistor, and wake up the device when the pin is low. 

- `Twitch` configures the pin so that the wakeup condition is true as soon as the device goes to sleep. This can be useful
if your script go into another mode if a condition is met.

## rtcmem()

This function reads the persistent memory of the NRF52 which only consists of 2 8bit bytes. Similar to the Esp32's
machine.RTC().memory() if you don't enter parameters, the function will return what is in the memory, and if you give it
bytes as parameters, it will record them in the memory.

## read_uicr(n)
UICRs are user registers provided by the NRF52. These registers are 32bits long and are non-volatile.

- `n` number from 0 to 31

## burnin_uicr(n, val)
UICRs are user registers provided by the NRF52. These registers are 32bits long and are non-volatile. They *are*
erasable, but I used the name "burn in" as you need to erase the chip completely to erase them with a Nrf debugger. So 
they should almost be considered as permanent unless you know what you are doing.

- `n` register number form 0 to 31
- `val` the value you want to put in the given register. It must be bytes or a bytearray of 4 8bit bytes.

## mktime(time_tuple)
This essentially converts a time.localtime() tuple into a micropython timestamp integer.

- `time_tuple` a tuple in the format (year, month, mday, hour, minute, second, weekday, yearday)

## localtime(seconds)
This function converts a micropython timestamp integer into a time.localtime() tuple.
- `seconds` a micropython timestamp integer

## SleepMemory Class

```python
sm = SleepMemory(7,1)
```
This class is used to manage retained ram sectors when the system is off. Be aware that retaining ram sectors during sleep
will make your chip consume more current while sleeping. Also, sectors from ram 8 will consume more current as they are
bigger. Refer to the NRF52840's datasheet for more information.

>[!NOTE] 
> Since this file is not an attempt to write a custom version of micropython or the Nrf52's bootloader, whatever you leave
> in these ram addresses once your device has booted up and is running your program. I made this SleepMemory class more 
> like a helper to pass memory from the last instant the chip is going to sleep, and that gets recovered in boot.py.

### \__init__(ram, sector)
- `ram` is the ram number where you want your retained information to go
- `sector` which sector you want to keep up during sleep

Refer to the datasheet for more details about the ram and sectors

### getting a value
```python
sm.value
sm[3:9]
```
you can either retrieve a value with the value property or with the slice notation.

### setting a value
```python
sm.value = b'\x01\x02\x03\x04'
sm[0:4] = b'\x0A\x0B\x0C\x0D'
```
You can either set the whole memory sector with the value property, or set a slice of it

### set_retain()
This function configures the NRF52 to retain the ram sector during deepsleep. It's very important to call this function
before going to deepsleep if you want to keep the memory.