import memregs, time

memory = bytearray(24)
header = memregs.Pack('HEADER', memory, 0, ('INITD', 1, True), ('MNT', 1, True), ('TYPE', 5), ('DATE', 1, False, 'H'), ('SAC', 3), span =16 )
header['DATE'] = time.time()
header['INITD'] = 1
header['TYPE'] = 'table'
header.post_all()

register = memregs.Struct('REGISTER', memory, 16, ('START',1, True), ('STATUS', 1,True), span = 8)
register.toggle('STATUS')
register.post_all()

print(f'Header :{memory[0:16]} \n\rregister : {memory[16:]}')