import re
from dataclasses import dataclass, field
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


@dataclass
class Chapter:
    title: str = field(default="")
    segments: List[TimeSegment] = field(default_factory=list)

    def check(self):
        assert "卷" in self.title, pformat(self.title)


@dataclass
class Book:
    chapters: List[Chapter] = field(default_factory=list)


book = Book()
pbar = tqdm(files[2:])
for f in pbar:
    cur_file = f
    pbar.set_description(f)
    lines = open(f, "r").readlines()
    chapter = Chapter()
    chapter.title = lines[0].strip("\n")
    i = 1
    lines_bar = tqdm(total=len(lines))
    lines_bar.update(1)
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
                lines_bar.update(i - lines_bar.n)
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
        lines_bar.update(i - lines_bar.n)

    book.chapters.append(chapter)
