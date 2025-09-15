# Memreg - Micropython Memory management library

Memreg is a library I developed after remarking that I kept having to make the same functions everytime I needed to manage
sessions or memory that has to persist during deepsleep or power cycles. Since most microcontrollers have a limited amount
of memory, I had to keep it small, and faster than using uctypes.structs.