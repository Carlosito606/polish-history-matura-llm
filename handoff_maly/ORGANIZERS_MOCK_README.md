# Download, solve, submit

This mock is the full May 2023 CKE history exam: 37 scored items, 60 points.
The website and guide are in English. Exam text and answers are in Polish.

1. Unzip the exam. Keep `exam.json` next to the `images/` folder.
2. For each item, send your solution `question`, `source_text`, and every linked PNG in `images`.
3. Fill `answers-template.json` with your solution's final answers. Rename it `answers.json`.
4. On the submissions page, enter your TEAM_KEY and solution name. Choose Mock exam and upload the JSON.
5. Keep your submission receipt. A successful upload means received, not graded.

Run on your laptop, AWS, Modal, or another environment. The submission service receives answers only.

## Exam format

`exam.json` contains `exam_id`, `instructions`, and `items`.
Each item has `id` (string), `group`, `max_points`, `question`, `source_text`, `images`, and `answer_format`.
Each image object contains a relative `path`, original `source_page`, and `sha256` checksum.
An empty `images` list means the item uses text only. Shared sources repeat across related items.
Read every source. Text and cropped illustrations are supplied separately; no PDF parsing is needed.
Labels within maps and diagrams remain part of their image. Scanned written sources have text transcriptions where supplied.
The essay is item `26`: choose one of the three topics and include its number and the entire essay in one answer.

This is the same exam used in the benchmark, in a NEW input format. The original image benchmark used full-page images. Its scores are not an identical-input comparison.

## Answer file

```json
{
  "exam_id": "history-2023-mock-v1",
  "answers": [
    {"id": "1", "answer": "Rozstrzygnięcie: ... Uzasadnienie: ..."},
    {"id": "2.1", "answer": "..."}
  ]
}
```

The snippet is shortened. Your file must contain ALL 37 IDs exactly once, using the supplied template. IDs remain strings (`"2.1"`, not `2.1`). Order does not matter.

- Each answer must be a string, including choices, true/false answers, and the essay.
- Use `""` when your solution cannot answer. The website warns about blanks but accepts them.
- Include only the final answer, without reasoning traces or chat logs.
- Answer in Polish. Keep all requested justifications.
- For choices/matching/true-false, follow the item's `answer_format`. Those examples show syntax, NOT solutions.
- Encode line breaks inside JSON strings as `\n`. Use a JSON library when writing the file.
- UTF-8 JSON, at most 1 MiB. Each answer allows up to 100,000 characters; essays are never silently cut.
- Only `exam_id` and `answers` are allowed at the top level. Each answer has only `id` and `answer`.
- Do not put TEAM_KEY, passwords, model weights, or API keys in the JSON.

Example Python:

```python
import json
from pathlib import Path
exam = json.loads(Path("exam.json").read_text(encoding="utf-8"))
answers = []
for item in exam["items"]:
    # Your harness reads item["question"], item["source_text"],
    # and the image files at image["path"] for image in item["images"].
    final_answer = solve(item)  # Implement this with your model/harness.
    answers.append({"id": item["id"], "answer": final_answer})
Path("answers.json").write_text(json.dumps({
    "exam_id": exam["exam_id"], "answers": answers
}, ensure_ascii=False, indent=2), encoding="utf-8")
```

## Feedback and grading

The page checks the exam ID, required question IDs, duplicates, field types, and size.
It does not judge correctness on upload. Organizers download the original answers and grade against the CKE rubric.
A failed upload keeps your selected file so you can retry. Repeated clicks/retries for the same request do not create a second submission.
The final exam is a separate pack and exam ID. Its download and upload remain locked until release by the organizers.
