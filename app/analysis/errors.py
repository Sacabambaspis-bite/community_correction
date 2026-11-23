"""不携带媒体内容、转写原文或绝对路径的分析异常。"""


class AnalysisError(Exception):
    """分析模块可预期异常的基类。"""


class AnalysisInputError(AnalysisError):
    """输入不满足采集状态、覆盖范围或路径约束。"""


class AnalysisSchemaError(AnalysisError):
    """Schema 加载或校验失败；消息仅含安全字段路径。"""
