import re
import json
import os
from dataclasses import dataclass, field, asdict
from typing import List
from glob import glob
from pprint import pformat

from tqdm import tqdm

PARA_IDX_PAT = re.compile("\[(\d+)\]")

files = glob("chapters/*.md")
cur_file = None


@dataclass
class CmpStr:
    original: str = field(default="")
    translated: str = field(default="")
    line_num: int = -1

    def check(self, **args):
        found = re.findall(PARA_IDX_PAT, self.original)
        if found:
            found_trans = re.findall(PARA_IDX_PAT, self.translated)
            assert (
                ("[todo]" in self.translated)
                or found_trans
                and (found[0] == found_trans[0])
            ), pformat([args, self, f"{cur_file}:{self.line_num}"])

        return True


@dataclass
class TimeSegment:
    start_time: CmpStr = field(default_factory=CmpStr)
    sentences: List[CmpStr] = field(default_factory=list)

    def check(self):
        assert re.findall("\d+", self.start_time.original) and re.findall(
            "\d+", self.start_time.translated
        ), pformat(self.start_time)

        for s in self.sentences:
            s.check(time=self.start_time)

    def __str__(self):
        return f"小节-起始时间 {self.start_time.translated.split(' ')[-1]}，包含 {len(self.sentences)} 句"


@dataclass
class Chapter:
    index: int = field(default=-1)
    title: str = field(default="")
    segments: List[TimeSegment] = field(default_factory=list)

    def check(self):
        assert "卷" in self.title, pformat(self.title)

    def __str__(self):
        return f"{self.title}（包含{len(self.segments)}小节）"


@dataclass
class Book:
    chapters: List[Chapter] = field(default_factory=list)


# Load the JSON file and convert back to Python objects
def json_to_book(file_path: str) -> Book:
    def cmpstr_from_dict(data):
        return CmpStr(**data)

    def timesegment_from_dict(data):
        return TimeSegment(
            start_time=cmpstr_from_dict(data["start_time"]),
            sentences=[cmpstr_from_dict(s) for s in data["sentences"]],
        )

    def chapter_from_dict(data):
        return Chapter(
            index=data["index"],
            title=data["title"],
            segments=[timesegment_from_dict(s) for s in data["segments"]],
        )

    def book_from_dict(data):
        return Book(chapters=[chapter_from_dict(c) for c in data["chapters"]])

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return book_from_dict(data)

if __name__ == "__main__":
    book = Book()
    pbar = tqdm(files)
    for f in pbar:
        cur_file = f
        pbar.set_description(f)
        lines = open(f, "r").readlines()
        chapter = Chapter()
        chapter.title = lines[0].strip("\n")
        chapter.index = int(f.split(os.sep)[-1].split("_")[0])
        i = 1
        # lines_bar = tqdm(total=len(lines))
        # lines_bar.update(1)
        while i < len(lines):
            line = lines[i]
            if line == "\n":
                i += 1
                continue
            if not line.startswith("\u3000\u3000"):
                ts = TimeSegment()
                ts.start_time = CmpStr(line.strip(), lines[i + 2].strip(), i)
                ts.check()
                i += 3
                while i < len(lines):
                    # lines_bar.update(i - lines_bar.n)
                    line = lines[i]
                    if line == "\n":
                        i += 1
                    elif not line.startswith("\u3000\u3000"):
                        i -= 1
                        break
                    elif line != "\n":
                        ts.sentences.append(CmpStr(line.strip(), lines[i + 2].strip(), i))
                        ts.sentences[-1].check(time=ts.start_time)
                        i += 3
                    else:
                        raise RuntimeError(lines[i])
                ts.check()
                chapter.segments.append(ts)
            else:
                raise RuntimeError(lines[i : i + 5])
            # lines_bar.update(i - lines_bar.n)

        book.chapters.append(chapter)

    book.chapters.sort(key=lambda x: x.index)
    json.dump(
        asdict(book), open("data.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False
    )
