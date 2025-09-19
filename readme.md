**# Memreg - Micropython Memory management library

Memreg is a library I developed after remarking that I kept having to make the same functions everytime I needed to manage
sessions or memory that has to persist during deepsleep or power cycles. Since most microcontrollers have a limited amount
of memory, I had to keep it small, and faster than using uctypes.structs.


Be aware that if you use memregs.Struct and that your items take more bytes than your memory area, it'll crash micropython
without throwing an exception.

`memregs.Struct` takes uctypes in ''
Is better for many items, and small updates

`memregs.Pack` takes struct.pack formats in ''
Is better for few items, and long updates. Its also more stable, but it takes more time and space.**

`memregs.CACHE` you can use it to change the file cache.

`clear_cache()` clears the cache in ram memory.

`delete_cache()` deletes the cache file.