class NoActiveLesson(Exception):
    def __init__(self):
        super().__init__("没有活跃课程")


class LessonConflict(Exception):
    def __init__(self, job_id: str | None = None):
        super().__init__("课程冲突" + (f" (job: {job_id})" if job_id else ""))
        self.job_id = job_id
