class AlreadyDefined(Exception):
    pass

class InvalidLine(Exception):
    pass

def readlines(filename):
    with open(filename, 'r') as stream:
        for line in stream:
            yield line.rstrip('\r\n')

def strip_comment(line):
    if line is None:
        return
    idx = line.find(';')
    if idx >= 0:
        line = line[:idx]

    line = line.strip()
    if len(line) > 0:
        return line

def extract_label(line, lineno, labels):
    if line is None:
        return
    start = line.find('&')

    if start >= 0:
        end = line.find(':')
        if end >= 0:
            label = line[start:end]
            if label in labels:
                raise AlreadyDefined
            else:
                labels[label] = lineno
    
    if start >= 0 and end >= 0:
        line = line[end+1:].strip()
        return line
    return line

def parse_operand(oprd, index, labels):
    if oprd is None:
        return
    adressing_mode = oprd[0]
    oprd = oprd[1:]
    value = None
    if oprd in labels:
        value = labels[oprd]
    else:
        value = int(oprd)

    value = value % (2**12)
    return adressing_mode, value

def parse_instruction(txt, index, labels):
    if txt is None:
        return
    details = txt.split()
    instruction = None
    operand1 = None
    operand2 = None


    for i, detail in enumerate(details):
        if i == 0:
            instruction = detail
        elif i == 1:
            operand1 = parse_operand(detail, index, labels)
        elif i == 2:
            operand2 = parse_operand(detail, index, labels)

    if instruction:
        return instruction, operand1, operand2


program0 = r'''
        MOV $127 r1  ; Initialize r1 to 127

&loop:  ADD $-1 r1   ; Decrement  r1 by 1
        BZ  $&end    ; If r1 is 0, move to end of program
        JMP $&loop   ; Otherwise, jump to loop

&end:   DIE
'''

program0 = program0.splitlines()
program1 = []
for x in program0:
    stripped = strip_comment(x)
    if stripped:
        program1.append(stripped)

labels   = {}
program2 = [extract_label(x, i, labels) for i, x in enumerate(program1)]

program3 = [parse_instruction(x, i, labels) for i, x in enumerate(program2)]

print(program3)
