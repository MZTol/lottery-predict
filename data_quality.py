import json
import os
from json import JSONDecodeError


HISTORY_RULES = {
    "kl8": {"numbers": (20, 1, 80)},
    "dlt": {"front": (5, 1, 35), "back": (2, 1, 12)},
    "ssq": {"front": (6, 1, 33), "back": (1, 1, 16)},
}


class DataQualityError(ValueError):
    pass


def validate_history(data, lotid):
    errors = []
    warnings = []
    rules = HISTORY_RULES.get(lotid, {})

    if not isinstance(data, list):
        return {"ok": False, "errors": ["历史数据不是数组"], "warnings": [], "count": 0}
    if not data:
        return {"ok": False, "errors": ["历史数据为空"], "warnings": [], "count": 0}

    seen_periods = set()
    previous_period = None
    for index, entry in enumerate(data):
        if not isinstance(entry, dict):
            errors.append(f"第{index + 1}条不是对象")
            continue

        period = str(entry.get("period", "")).strip()
        if not period.isdigit():
            errors.append(f"第{index + 1}条期号无效")
        elif period in seen_periods:
            errors.append(f"期号重复: {period}")
        else:
            seen_periods.add(period)
            current_period = int(period)
            if previous_period is not None and current_period >= previous_period:
                warnings.append(f"期号未严格从新到旧: {period}")
            previous_period = current_period

        for field, (expected_count, minimum, maximum) in rules.items():
            values = entry.get(field)
            if not isinstance(values, list):
                errors.append(f"{period or index + 1}期 {field} 不是数组")
                continue
            if len(values) != expected_count:
                errors.append(
                    f"{period or index + 1}期 {field} 应有{expected_count}个号码，实际{len(values)}个"
                )
            numbers = []
            for value in values:
                try:
                    number = int(value)
                except (TypeError, ValueError):
                    errors.append(f"{period or index + 1}期 {field} 含无效号码: {value}")
                    continue
                numbers.append(number)
                if not minimum <= number <= maximum:
                    errors.append(
                        f"{period or index + 1}期 {field} 号码越界: {number}"
                    )
            if len(numbers) != len(set(numbers)):
                errors.append(f"{period or index + 1}期 {field} 存在重复号码")

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "count": len(data),
    }


def load_history(filename, lotid):
    if not os.path.exists(filename):
        raise DataQualityError(f"历史文件不存在: {filename}")
    try:
        with open(filename) as f:
            data = json.load(f)
    except (OSError, JSONDecodeError) as exc:
        raise DataQualityError(f"历史文件无法解析: {filename}") from exc

    result = validate_history(data, lotid)
    if not result["ok"]:
        detail = "；".join(result["errors"][:3])
        raise DataQualityError(f"{filename} 数据校验失败: {detail}")
    return data, result
