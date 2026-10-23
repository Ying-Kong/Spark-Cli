"""Turn a target argument into a runnable file, mirroring the v1 rules."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class TargetError(RuntimeError):
    """The target cannot be resolved. The message is user facing."""


@dataclass(frozen=True)
class Target:
    path: str
    main_class: str | None
    is_jar: bool


def resolve(target: str, home: Path, main_class: str | None = None) -> Target:
    lower = target.lower().strip()

    if lower == "pi.jar":
        examples = home / "examples" / "jars"
        try:
            jar = next(examples.glob("spark-examples*.jar"))
        except StopIteration:
            msg = f"未找到 spark-examples.jar 包于 {examples}"
            raise TargetError(msg) from None
        return Target(str(jar), "org.apache.spark.examples.SparkPi", True)

    if lower == "pi.py":
        path = home / "examples" / "src" / "main" / "python" / "pi.py"
        if not path.exists():
            msg = f"未找到 Python 示例文件: {path}"
            raise TargetError(msg)
        return Target(str(path), None, False)

    if lower == "df.r":
        path = home / "examples" / "src" / "main" / "r" / "dataframe.R"
        if not path.exists():
            msg = f"未找到 R 示例文件: {path}"
            raise TargetError(msg)
        return Target(str(path), None, False)

    path = Path(target)
    if not path.exists():
        msg = f"错误: 目标文件或别名 '{target}' 不存在。"
        raise TargetError(msg)

    suffix = path.suffix.lower()
    if suffix == ".jar":
        if not main_class:
            msg = "错误: 运行自定义 JAR 包必须通过 -c 或 --main-class 指定主类名。"
            raise TargetError(msg)
        return Target(str(path.resolve()), main_class, True)
    if suffix not in (".py", ".r"):
        msg = f"错误: 不支持的文件类型 '{suffix}'。"
        raise TargetError(msg)
    return Target(str(path.resolve()), None, False)
