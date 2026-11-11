from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError


def decimal_value(value, *, positive=False):
    # Giao tiếp web nên truyền chuỗi thập phân hoặc Decimal, không dùng float tiền tệ.
    if isinstance(value, bool) or isinstance(value, float):
        raise ValidationError('Hãy truyền số nguyên, chuỗi thập phân hoặc Decimal.')
    try:
        number = Decimal(value)
        if not number.is_finite() or number < 0 or (positive and number == 0):
            raise ValidationError('Số lượng/đơn giá không hợp lệ.')
        if number != number.quantize(Decimal('0.01')):
            raise ValidationError('Chỉ cho phép tối đa 2 chữ số thập phân.')
        return number
    except (TypeError, ValueError, InvalidOperation):
        raise ValidationError('Giá trị thập phân không hợp lệ.')


def integer_value(value, minimum=0, maximum=None):
    if type(value) is not int or value < minimum or (maximum is not None and value > maximum):
        raise ValidationError(f'Nhập số nguyên từ {minimum} đến {maximum}.' if maximum is not None else f'Nhập số nguyên từ {minimum}.')
    return value


def unique_lines(lines, *, allow_empty=False):
    lines = list(lines)
    if not lines and not allow_empty:
        raise ValidationError('Chứng từ phải có ít nhất một dòng chi tiết.')
    ids = [line.get('item_id') for line in lines]
    if any(type(pk) is not int or pk <= 0 for pk in ids):
        raise ValidationError('Vui lòng chọn mặt hàng hợp lệ.')
    if len(ids) != len(set(ids)):
        raise ValidationError('SKU đã có ở dòng khác.')
    return lines, ids


def is_whole(value):
    try:
        value = Decimal(str(value))
        return value.is_finite() and value == value.to_integral_value()
    except (ValueError, TypeError, InvalidOperation):
        return False
