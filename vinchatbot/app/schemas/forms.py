from __future__ import annotations

from pydantic import BaseModel, Field

# Output file formats the Form Assistant can return. "pdf" = the official fillable AcroForm PDF filled
# in-place (pixel-perfect); "docx" = a clean, editable document generated from the form's fields when the
# official file is flat / not fillable (or fetch/parse failed). The frontend uses this to name the download.
FORM_FILE_KINDS = {"pdf", "docx"}


class FormField(BaseModel):
    """One fillable field on a form. `key` is stable (the AcroForm widget name when present, otherwise a
    synthesized slug); `label` is what the student sees; `value` is the (pre)filled text."""

    key: str = Field(min_length=1, max_length=200)
    label: str = Field(default="", max_length=300)
    value: str = Field(default="", max_length=5000)


class SuggestFormRequest(BaseModel):
    """Input for `POST /forms/suggest`: the official form to draft + the conversation that prompted it. The
    backend fetches `official_url`, extracts its fields, and fills them with the student's data + request."""

    official_url: str = Field(min_length=1, max_length=2000)
    form_title: str | None = Field(default=None, max_length=300)
    origin_question: str = Field(min_length=1, max_length=2000)
    answer: str | None = Field(default=None, max_length=8000)
    context: str | None = Field(default=None, max_length=8000)


class SuggestedFormFill(BaseModel):
    """A drafted, review-ready form: the fields (pre-filled) the student edits before downloading."""

    form_title: str = Field(max_length=300)
    official_url: str = Field(max_length=2000)
    file_kind: str = Field(default="docx", max_length=8)
    fields: list[FormField] = Field(default_factory=list)
    narrative: str = Field(default="", max_length=5000)
    created_by_ai: bool = False
    # Human-readable note when we could not fill the official PDF in-place and generated an editable .docx
    # instead (so the drawer can tell the student the download is a clean copy, not the original template).
    notice: str | None = Field(default=None, max_length=500)


class FillFormRequest(BaseModel):
    """Input for `POST /forms/fill`: produce the downloadable file from the (possibly student-edited) fields.
    `file_kind` "auto" lets the backend pick (fill the official PDF if fillable, else generate a .docx)."""

    official_url: str = Field(min_length=1, max_length=2000)
    form_title: str | None = Field(default=None, max_length=300)
    file_kind: str = Field(default="auto", max_length=8)
    fields: list[FormField] = Field(default_factory=list)
