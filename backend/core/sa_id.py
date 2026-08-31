"""Parse and checksum South African ID numbers locally (no Home Affairs call)."""
from datetime import date


def digits_only(value):
    return ''.join(ch for ch in (value or '') if ch.isdigit())


def luhn_ok(number_str):
    digits = [int(ch) for ch in number_str]
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def parse_sa_id(raw):
    """Return DOB, sex and Luhn result for a 13-digit SA ID. Never calls the internet."""
    digits = digits_only(raw)
    result = {
        'digits': digits,
        'is_sa_length': len(digits) == 13,
        'luhn_ok': False,
        'dob': None,
        'sex': '',
        'citizen': '',
        'message': '',
    }
    if len(digits) != 13:
        if digits:
            result['message'] = 'A South African ID has 13 digits. This still saves as typed.'
        return result
    if not luhn_ok(digits):
        result['message'] = 'This ID fails the checksum used on South African IDs. Check the digits.'
        return result
    result['luhn_ok'] = True
    yy, mm, dd = int(digits[0:2]), int(digits[2:4]), int(digits[4:6])
    today = date.today()
    dob = None
    for century in (2000, 1900):
        try:
            candidate = date(century + yy, mm, dd)
        except ValueError:
            continue
        age = today.year - candidate.year - ((today.month, today.day) < (candidate.month, candidate.day))
        if 0 <= age <= 120 and candidate <= today:
            dob = candidate
            if century == 2000:
                break
    result['dob'] = dob.isoformat() if dob else None
    seq = int(digits[6:10])
    result['sex'] = 'Female' if seq < 5000 else 'Male'
    result['citizen'] = 'South African' if digits[10] == '0' else 'Permanent resident / other'
    if not dob:
        result['message'] = 'Checksum is valid but the date-of-birth digits are not a real date.'
    else:
        result['message'] = 'Valid South African ID checksum.'
    return result
