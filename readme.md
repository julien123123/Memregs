# Memreg - Micropython Memory management library

Memreg is a library I developed after remarking that I kept having to make the same functions everytime I needed to manage
sessions or memory that has to persist during deepsleep or power cycles. Since most microcontrollers have a limited amount
of memory, I had to keep it small, and fast.


```python
import memregs, time

memory = bytearray(24)
header = memregs.Pack('HEADER', memory, 0, ('INITD', 1, True), ('MNT', 1, True), ('TYPE', 5), ('DATE', 1, False, 'H'), span =16 )
header['DATE'] = time.time()
header['INITD'] = 1
header['TYPE'] = 'table'
header.post_all()

register = memregs.Struct('REGISTER', memory, 16, ('START',1, True), ('STATUS', 1,True), span = 8)
register.toggle('STATUS')
register.post_all()

print(f'Header :{memory[0:16]} \n\rregister : {memory[16:]}')
```
>[!WARNING] if the memory bytearray is not big enough for all the arguments, it won't throw an error, Micropython on you microcontroller will just crashé

## memregs.Struct
This class is based un uctypes.struct. It's very very fast, and it's a better choice for many items, and small updates. be aware that it's very fickle, and it may crash micropython if there's an error in your code.
```python
memregs.Struct(name = '', mem = bytearray(), offset = 0, args = (name = '', span = 1, bin = False, format = 'UINT8'), span = 32)
```
`name` [*str*] : name

`mem` [*obj with buffre protocol*] : most likely a byte array or a memory location like nvm or deepsleep memory
>[!NOTE] every memregs class uses bytearray buffer to prevent crashing you microcontroller when changing individual values

`offset` [*int*] Where the first byte of the memory array is

`span` [*int* defaults to *32*] The number of bytes in the memregs registers so. Both offset and span define where your memreg start and ends in the memory you define.

### args
keywords arguments here are just for demonstration, do not use them in code. you can put as many as 255 in parenthesis.

`name` [*str* mandatory] Name of the item of the memreg. This is used to retrieve and save the values in the memregs with `register['name']`

`span` [*int* manatory] Number of bytes if you item is not binary. If that item is binary, this represents the number of bits.

`bin` [*bool* defaults to False] Is this item bianry values?

`format` [*str* defaults to False] the uctype type of the item (minus the "uctypes." part of the type). For more info, see micropython uctypes module in micropython docs.

### memregs.OrderedStrut
This is exactly the same as `Struct`, but instead of optimising the order of the items, the are ordered exclty how you declared them when creating the memregs object. This might be more useful for hardware registers.

## memregs.Pack
This class is based on struct.pack/unpack. It's faster at changing many long values. This class might also be safer for mistakes
```python
memregs.Pack(name = 'name', mem = bytearray(), offset = 0, args = (name = '', span = 1, bin = True, format = 'B'), span = 32 )
```
>[!NOTE] This class is a bit slower in general, but is easier to debug

`name` [*str*] : name

`mem` [*obj with buffre protocol*] : most likely a byte array or a memory location like nvm or deepsleep memory
>[!NOTE] every memregs class uses bytearray buffer to prevent crashing you microcontroller when changing individual values

`offset` [*int*] Where the first byte of the memory array is

`span` [*int* defaults to *32*] The number of bytes in the memregs registers so. Both offset and span define where your memreg start and ends in the memory you define.

### args
keywords arguments here are just for demonstration, do not use them in code. you can put as many as 255 in parenthesis.

`name` [*str* mandatory] Name of the item of the memreg. This is used to retrieve and save the values in the memregs with `register['name']`

`span` [*int* manatory] Number of bytes if you item is not binary. If that item is binary, this represents the number of bits. Be aware that the span will be multiplied by the length of bytes you chose in the format parameter because bytearrays in python always use 8 bits bytes.

`bin` [*bool* defaults to False] Is this item bianry values?

`format` [*str* defaults to False] The struct.pack format of the byte if it's not binary. For more info, see micropython struct module in micropython/cpython docs. This module doesn't accetpt more than one byte format written one after the other like struct.pak

### memregs.OrderedPack
This is exactly the same as `Pack`, but instead of optimising the order of the items to put the binary values togeher, this class orders the items exactly like you declare them when you declare the class object. This is more useful for hardware registers.

## Cache

This module uses a cache in order to save on resources once you created your memregs. This is especially useful for session metadata if you microcontroller works on batteries or you frequently send it to sleep.

`memregs.CACHE` you can use it to change the file cache. The cache itself is stored in 'memcache.txt' by default.

`memregs.clear_cache()` clears the cache in ram memory.

`memregs.delete_cache()` deletes the cache file.