"""Parse and checksum South African ID numbers locally (no Home Affairs call).

A South African ID is 13 digits: YYMMDD (6) + sequence (4) + citizenship (1)
+ a spare digit + a Luhn check digit. Anything that is not exactly 13 digits
cannot be read as an ID at all, and a 13-digit number that fails the date or
the checksum must not be used to work out a date of birth or a sex.
"""
from datetime import date

SA_ID_LENGTH = 13
MAX_AGE_YEARS = 120

CITIZENSHIP = {
    '0': 'South African citizen',
    '1': 'Permanent resident',
    '2': 'Refugee',
}


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


def id_digits(raw):
    """Spaces and dashes stripped. Returns '' unless exactly 13 digits remain.

    A partial read is not a shortened ID, it is an unreadable one, so nothing
    downstream should ever see '74' or '019042' in an ID field.
    """
    digits = digits_only(raw)
    return digits if len(digits) == SA_ID_LENGTH else ''


def _dob_from_digits(digits, today=None):
    """YYMMDD with the century chosen so the date is real and not in the future."""
    today = today or date.today()
    yy, mm, dd = int(digits[0:2]), int(digits[2:4]), int(digits[4:6])
    for century in (2000, 1900):
        try:
            candidate = date(century + yy, mm, dd)
        except ValueError:
            continue
        if candidate > today:
            continue
        age = today.year - candidate.year - (
            (today.month, today.day) < (candidate.month, candidate.day)
        )
        if age <= MAX_AGE_YEARS:
            return candidate
    return None


def parse_sa_id(raw, today=None):
    """Check one SA ID against every rule. Never calls the internet."""
    digits = digits_only(raw)
    result = {
        'digits': digits,
        'is_sa_length': len(digits) == SA_ID_LENGTH,
        'luhn_ok': False,
        'date_ok': False,
        'valid': False,
        'dob': None,
        'sex': '',
        'citizen': '',
        'citizenship': '',
        'problems': [],
        'message': '',
    }
    if len(digits) != SA_ID_LENGTH:
        if digits:
            result['problems'].append(
                f'{len(digits)} digits were read and a South African ID has {SA_ID_LENGTH}'
            )
            result['message'] = (
                f'A South African ID has {SA_ID_LENGTH} digits, so this cannot be read as '
                'one. Type the number from the document.'
            )
        return result

    dob = _dob_from_digits(digits, today=today)
    result['date_ok'] = dob is not None
    if dob is None:
        result['problems'].append('the first six digits are not a real date of birth')

    citizenship = CITIZENSHIP.get(digits[10], '')
    if citizenship:
        result['citizenship'] = citizenship
        result['citizen'] = 'South African' if digits[10] == '0' else citizenship
    else:
        result['problems'].append(
            f'digit 11 is {digits[10]}, which is not 0 (citizen), 1 (permanent resident) '
            'or 2 (refugee)'
        )

    result['luhn_ok'] = luhn_ok(digits)
    if not result['luhn_ok']:
        result['problems'].append('the last digit does not check out against the other twelve')

    if result['problems']:
        # Deliberately leaves dob and sex unset: an ID that fails these rules
        # must not be used to work either of them out.
        result['message'] = (
            'This is 13 digits but not a valid South African ID - '
            + '; '.join(result['problems'])
            + '. Check it against the document.'
        )
        return result

    result['valid'] = True
    result['dob'] = dob.isoformat()
    result['sex'] = 'Female' if int(digits[6:10]) < 5000 else 'Male'
    result['message'] = 'Valid South African ID checksum.'
    return result
