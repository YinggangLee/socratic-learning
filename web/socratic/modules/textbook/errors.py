class TextbookNotFound(Exception):
    def __init__(self, textbook_id: str):
        super().__init__(f"教材未找到: {textbook_id}")
        self.textbook_id = textbook_id


class InvalidTextbookStatus(Exception):
    def __init__(self, current: str, target: str, reason: str = ""):
        msg = f"无法从 {current} 切换为 {target}"
        if reason:
            msg += f": {reason}"
        super().__init__(msg)
        self.current = current
        self.target = target


class TextbookImportFailed(Exception):
    def __init__(self, textbook_id: str, error: str):
        super().__init__(f"教材导入失败 {textbook_id}: {error}")
        self.textbook_id = textbook_id
        self.error = error
