import re
_re_label = re.compile("([0-9]+)([A-Z\\-]+)")
_base = 26
_depth = 3

def _compute_max_letter_order(b):
    if b == 1:
        return _base
    else:
        return _base + _base*_compute_max_letter_order(b-1)

_max_letter_order = _compute_max_letter_order(_depth)

def position_to_letters(p):
    if p < _base:
        return chr(ord('A') + p)
    else:
        return position_to_letters(p // _base - 1) + position_to_letters( p % _base)


def _letters_to_order(m, base=_depth):

    if len(m) <= base:
        m = m + '-' * (base - len(m))
    else:
        raise Exception("The letter part of a label ({}) is too long".format(m))

    position = 0
    b = 1
    for i in reversed(range(len(m))):
        f = 0
        if m[i] != '-':
            # A = 1, Z = _base
            f = ord(m[i]) - ord('A') + 1
        # print("{} {} {}".format(i,f,b))

        position -= b * f
        b = b * _base

    # print("return:{}".format(position))
    return position + _max_letter_order


def label_to_key(label):
    number, letter = _re_label.match(label).groups()

    return int(number) * _max_letter_order + _letters_to_order(letter)



def compare_labels(a,b):

    # in Python 2, cmp's behaviour is not defined for None values

    if not a and not b:
        return 0

    if not a:
        return -1

    if not b:
        return +1

    a_base, a_op = _re_label.match(a).groups()
    b_base, b_op = _re_label.match(b).groups()

    return cmp(int(a_base),int(b_base)) or cmp(len(a_op),len(b_op)) or cmp(a_op,b_op)
