class InvalidInstruction(Exception):
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

from corewar import of_signed

def parse_operand(oprd, index, labels):
    if oprd is None:
        return

    adressing_mode = oprd[0]
    oprd = oprd[1:]
    if oprd in labels:
        value = labels[oprd] - index
    else:
        value = int(oprd)

    if value < 0:
        value = of_signed(value, 12)
    else:
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

def is_writable(operand):
    if operand[0] == '$':
        return False
    elif operand[0] in ['@', '#', 'r']:
        return True
    else:
        raise InvalidInstruction

def validate_instruction(inst):
    name, op1, op2 = inst

    if name in ['FORK', 'DIE']:
        if op1 or op2:
            raise InvalidInstruction

    elif name in ['MOV', 'ADD', 'SUB', 'NOT', 'AND', 'OR', 'LS', 'AS']:
        if not op1 or not op2:
            raise InvalidInstruction
        if not is_writable(op2):
            raise InvalidInstruction
    
    elif name in ['CMP', 'LT']:
        if not op1 or not op2:
            raise InvalidInstruction

    elif name in ['POP']:
        if not op1 or op2:
            raise InvalidInstruction
        if not is_writable(op1):
            raise InvalidInstruction

    elif name in ['PUSH', 'JMP', 'BZ']:
        if not op1 or op2:
            raise InvalidInstruction
    
    else:
        raise InvalidInstruction

def instruction_name_code(name):
    return ['FORK', 'MOV', 'NOT', 'AND', 'OR', 'LS', 'AS', 'ADD',\
        'SUB', 'CMP', 'LT', 'POP', 'PUSH', 'JMP', 'BZ', 'DIE'].index(name)

def operand_mode_code(mode):
    return ['$', '@', '#', 'r'].index(mode)

def instruction_code(instr):
    name = instruction_name_code(instr[0])

    if not instr[1]:
        opAmode, opA = 0, 0
    else:
        opAmode = operand_mode_code(instr[1][0]) << 4
        opA = instr[1][1] << 8

    if not instr[2]:
        opBmode, opB = 0, 0
    else:
        opBmode = operand_mode_code(instr[2][0]) << 6
        opB = instr[2][1] << 20

    return name + opAmode + opA + opBmode + opB

def assembler(filename):
    labels, lineno, src, codes, aout = {}, 0, [], [], bytearray()
    with open(filename, 'r') as stream:
        for line in stream:
            line = strip_comment(line)
            if line is not None:
                src.append(extract_label(line, lineno, labels))
                lineno += 1
    for i, line in enumerate(src):
        instr = parse_instruction(line, i, labels)
        validate_instruction(instr)
        codes.append(instruction_code(instr))
    for i in codes:
        aout.extend(int.to_bytes(i, 4, 'little'))
    return bytes(aout)
