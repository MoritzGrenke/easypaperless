"""Tests for the tasks resource (issue #0045)."""

from __future__ import annotations

import inspect
import json
import time
from pathlib import Path

import httpx
import pytest

import easypaperless
import easypaperless.models as models
import easypaperless.models.documents as documents_models
import easypaperless.models.tasks as tasks_models
from easypaperless import Document, PagedResult, Task, TaskStatus
from easypaperless.exceptions import NotFoundError, TaskTimeoutError, UploadError
from easypaperless.resources import SyncTasksResource, TasksResource
from tests._transport import FakePaperless

TASK_UUID = "c9d6a2a4-1f5e-4a8b-9a3e-2f7d1e0b6c11"

TASKS_PATH = ("GET", "/api/tasks/")


def task_json(**overrides: object) -> dict[str, object]:
    """A task as returned by ``GET /api/tasks/?task_id=...`` (paperless-ngx 2.x)."""
    task: dict[str, object] = {
        "id": 17,
        "task_id": TASK_UUID,
        "task_name": "consume_file",
        "task_file_name": "invoice.pdf",
        "date_created": "2026-10-20T10:00:00.123456+02:00",
        "date_done": "2026-10-20T10:00:09.654321+02:00",
        "type": "file",
        "status": "SUCCESS",
        "result": "Success. New document id 42 created",
        "acknowledged": False,
        "related_document": "42",
        "owner": 3,
    }
    task.update(overrides)
    return task


async def test_get_returns_task_populated_from_response() -> None:
    fake = FakePaperless({TASKS_PATH: [task_json()]})
    async with fake.async_client() as client:
        task = await client.tasks.get(TASK_UUID)

    assert isinstance(task, Task)
    assert task.id == 17
    assert task.task_id == TASK_UUID
    assert task.task_name == "consume_file"
    assert task.task_file_name == "invoice.pdf"
    assert task.status == TaskStatus.SUCCESS
    assert task.result == "Success. New document id 42 created"
    assert task.related_document == "42"
    assert task.acknowledged is False
    assert task.owner == 3
    assert task.date_done is not None
    assert fake.requests[0].url.params["task_id"] == TASK_UUID


async def test_get_unknown_task_raises_not_found() -> None:
    fake = FakePaperless({TASKS_PATH: []})
    async with fake.async_client() as client:
        with pytest.raises(NotFoundError, match="unknown-id"):
            await client.tasks.get("unknown-id")


async def test_list_wraps_plain_array_in_paged_result_without_filters() -> None:
    other = task_json(id=18, task_id="other-uuid", status="PENDING", related_document=None)
    fake = FakePaperless({TASKS_PATH: [task_json(), other]})
    async with fake.async_client() as client:
        result = await client.tasks.list()

    assert isinstance(result, PagedResult)
    assert result.count == 2
    assert result.next is None and result.previous is None
    assert [t.task_id for t in result.results] == [TASK_UUID, "other-uuid"]
    assert result.results[1].status == TaskStatus.PENDING
    assert dict(fake.requests[0].url.params) == {}


async def test_list_sends_paperless_filter_parameters() -> None:
    fake = FakePaperless({TASKS_PATH: []})
    async with fake.async_client() as client:
        await client.tasks.list(
            task_id=TASK_UUID,
            status=TaskStatus.FAILURE,
            task_name="consume_file",
            type="file",
            acknowledged=False,
        )

    assert dict(fake.requests[0].url.params) == {
        "task_id": TASK_UUID,
        "status": "FAILURE",
        "task_name": "consume_file",
        "type": "file",
        "acknowledged": "false",
    }


async def test_list_accepts_status_as_plain_string_and_acknowledged_true() -> None:
    fake = FakePaperless({TASKS_PATH: []})
    async with fake.async_client() as client:
        await client.tasks.list(status="SUCCESS", acknowledged=True)

    assert dict(fake.requests[0].url.params) == {"status": "SUCCESS", "acknowledged": "true"}


async def test_list_accepts_paginated_envelope_and_follows_next_pages() -> None:
    page2_url = "http://paperless.test/api/tasks/?page=2"
    fake = FakePaperless(
        {
            TASKS_PATH: FakePaperless.seq(
                {"count": 2, "next": page2_url, "previous": None, "results": [task_json()]},
                {
                    "count": 2,
                    "next": None,
                    "previous": "http://paperless.test/api/tasks/",
                    "results": [task_json(id=18, task_id="other-uuid")],
                },
            )
        }
    )
    async with fake.async_client() as client:
        result = await client.tasks.list()

    assert result.count == 2
    assert [t.id for t in result.results] == [17, 18]
    assert result.next is None


# --- wait() -------------------------------------------------------------------

FAST = 0.001  # poll_interval for tests: never sleep for real for long

# Recorded-style paperless-ngx failure results (consumer messages, paperless-ngx 2.x).
DUPLICATE_RESULT = "Not consuming invoice.pdf: It is a duplicate of Invoice 2026-10 (#12)."
OCR_FAILURE_RESULT = (
    "invoice.pdf: Error occurred while consuming document invoice.pdf: "
    "Error while performing OCR: SubprocessOutputError"
)


def pending(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "status": "PENDING",
        "result": None,
        "related_document": None,
        "date_done": None,
    }
    base.update(overrides)
    return task_json(**base)


async def test_wait_polls_until_success_and_returns_final_task() -> None:
    fake = FakePaperless(
        {
            TASKS_PATH: FakePaperless.seq(
                [],  # task not registered yet right after the upload
                [pending()],
                [pending(status="STARTED")],
                [task_json()],
            )
        }
    )
    async with fake.async_client() as client:
        task = await client.tasks.wait(TASK_UUID, poll_interval=FAST)

    assert task.status == TaskStatus.SUCCESS
    assert task.related_document == "42"
    assert len(fake.requests) == 4
    assert all(r.url.params["task_id"] == TASK_UUID for r in fake.requests)


@pytest.mark.parametrize("status", ["FAILURE", "REVOKED"])
async def test_wait_raises_upload_error_carrying_unaltered_task(status: str) -> None:
    failed = task_json(status=status, result=OCR_FAILURE_RESULT, related_document=None)
    fake = FakePaperless({TASKS_PATH: FakePaperless.seq([pending()], [failed])})
    async with fake.async_client() as client:
        with pytest.raises(UploadError) as exc_info:
            await client.tasks.wait(TASK_UUID, poll_interval=FAST)

    err = exc_info.value
    assert err.task is not None
    assert err.task.task_id == TASK_UUID
    assert err.task.status == status
    assert err.task.result == OCR_FAILURE_RESULT


async def test_duplicate_and_ocr_failure_are_distinguishable_by_task_result() -> None:
    results = {}
    for name, message in [("duplicate", DUPLICATE_RESULT), ("ocr", OCR_FAILURE_RESULT)]:
        failed = task_json(status="FAILURE", result=message, related_document=None)
        fake = FakePaperless({TASKS_PATH: [failed]})
        async with fake.async_client() as client:
            with pytest.raises(UploadError) as exc_info:
                await client.tasks.wait(TASK_UUID, poll_interval=FAST)
        assert exc_info.value.task is not None
        results[name] = exc_info.value.task.result

    assert results["duplicate"] == DUPLICATE_RESULT
    assert "duplicate" in (results["duplicate"] or "").lower()
    assert results["ocr"] == OCR_FAILURE_RESULT
    assert "duplicate" not in (results["ocr"] or "").lower()


async def test_wait_per_call_poll_timeout_raises_task_timeout_error_with_task_id() -> None:
    fake = FakePaperless({TASKS_PATH: [pending()]})
    # Client defaults would wait a minute; the per-call values must win.
    async with fake.async_client(poll_interval=30.0, poll_timeout=60.0) as client:
        start = time.monotonic()
        with pytest.raises(TaskTimeoutError) as exc_info:
            await client.tasks.wait(TASK_UUID, poll_interval=FAST, poll_timeout=0.05)
        elapsed = time.monotonic() - start

    assert exc_info.value.task_id == TASK_UUID
    assert exc_info.value.timeout == 0.05
    assert 0.05 <= elapsed < 2.0
    assert len(fake.requests) > 1  # polled repeatedly at the per-call interval


async def test_wait_uses_client_defaults_when_not_given() -> None:
    fake = FakePaperless({TASKS_PATH: [pending()]})
    async with fake.async_client(poll_interval=FAST, poll_timeout=0.05) as client:
        with pytest.raises(TaskTimeoutError) as exc_info:
            await client.tasks.wait(TASK_UUID)

    assert exc_info.value.task_id == TASK_UUID
    assert exc_info.value.timeout == 0.05


async def test_wait_can_resume_after_timeout() -> None:
    fake = FakePaperless({TASKS_PATH: FakePaperless.seq([pending()], [pending()], [task_json()])})
    async with fake.async_client(poll_interval=FAST) as client:
        try:
            await client.tasks.wait(TASK_UUID, poll_timeout=0.0)
            raise AssertionError("expected TaskTimeoutError")
        except TaskTimeoutError as err:
            task = await client.tasks.wait(err.task_id or "", poll_timeout=5.0)

    assert task.status == TaskStatus.SUCCESS


# --- acknowledge() --------------------------------------------------------------


async def test_acknowledge_posts_task_ids_and_returns_count() -> None:
    fake = FakePaperless({("POST", "/api/tasks/acknowledge/"): {"result": 2}})
    async with fake.async_client() as client:
        count = await client.tasks.acknowledge([1, 2])

    assert count == 2
    assert json.loads(fake.requests[0].content) == {"tasks": [1, 2]}


# --- documents.upload() on top of tasks.wait() ---------------------------------

UPLOAD_PATH = ("POST", "/api/documents/post_document/")
DOCUMENT = {"id": 42, "title": "Invoice", "tags": []}


async def test_upload_wait_false_still_returns_task_id(tmp_path: Path) -> None:
    pdf = tmp_path / "invoice.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    fake = FakePaperless({UPLOAD_PATH: httpx.Response(200, json=TASK_UUID)})
    async with fake.async_client() as client:
        result = await client.documents.upload(pdf)

    assert result == TASK_UUID
    assert len(fake.requests) == 1


async def test_upload_wait_true_returns_document_via_task(tmp_path: Path) -> None:
    pdf = tmp_path / "invoice.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    fake = FakePaperless(
        {
            UPLOAD_PATH: httpx.Response(200, json=TASK_UUID),
            TASKS_PATH: FakePaperless.seq([pending()], [task_json()]),
            ("GET", "/api/documents/42/"): DOCUMENT,
        }
    )
    async with fake.async_client() as client:
        doc = await client.documents.upload(pdf, wait=True, poll_interval=FAST)

    assert isinstance(doc, Document)
    assert doc.id == 42


async def test_upload_wait_true_duplicate_failure_carries_task(tmp_path: Path) -> None:
    pdf = tmp_path / "invoice.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    failed = task_json(status="FAILURE", result=DUPLICATE_RESULT, related_document=None)
    fake = FakePaperless({UPLOAD_PATH: httpx.Response(200, json=TASK_UUID), TASKS_PATH: [failed]})
    async with fake.async_client() as client:
        with pytest.raises(UploadError) as exc_info:
            await client.documents.upload(pdf, wait=True, poll_interval=FAST)

    assert exc_info.value.task is not None
    assert exc_info.value.task.result == DUPLICATE_RESULT


async def test_upload_wait_true_timeout_carries_task_id(tmp_path: Path) -> None:
    pdf = tmp_path / "invoice.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    fake = FakePaperless(
        {UPLOAD_PATH: httpx.Response(200, json=TASK_UUID), TASKS_PATH: [pending()]}
    )
    async with fake.async_client() as client:
        with pytest.raises(TaskTimeoutError) as exc_info:
            await client.documents.upload(pdf, wait=True, poll_interval=FAST, poll_timeout=0.02)

    assert exc_info.value.task_id == TASK_UUID
    assert exc_info.value.timeout == 0.02


async def test_upload_wait_true_success_without_document_carries_task(tmp_path: Path) -> None:
    pdf = tmp_path / "invoice.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    fake = FakePaperless(
        {
            UPLOAD_PATH: httpx.Response(200, json=TASK_UUID),
            TASKS_PATH: [task_json(related_document=None)],
        }
    )
    async with fake.async_client() as client:
        with pytest.raises(UploadError, match="no document ID") as exc_info:
            await client.documents.upload(pdf, wait=True, poll_interval=FAST)

    assert exc_info.value.task is not None
    assert exc_info.value.task.status == TaskStatus.SUCCESS


# --- sync client ----------------------------------------------------------------


def test_sync_client_provides_identical_tasks_api() -> None:
    for name in ("list", "get", "wait", "acknowledge"):
        async_sig = inspect.signature(getattr(TasksResource, name))
        sync_sig = inspect.signature(getattr(SyncTasksResource, name))
        assert async_sig.parameters.keys() == sync_sig.parameters.keys(), name
        for param in async_sig.parameters.values():
            assert sync_sig.parameters[param.name].default == param.default, (name, param)
        assert getattr(SyncTasksResource, name).__doc__, name


def test_sync_tasks_list_get_wait_acknowledge() -> None:
    fake = FakePaperless(
        {
            TASKS_PATH: FakePaperless.seq([task_json()], [task_json()], [pending()], [task_json()]),
            ("POST", "/api/tasks/acknowledge/"): {"result": 1},
        }
    )
    with fake.sync_client(poll_interval=FAST) as client:
        listed = client.tasks.list(acknowledged=False)
        task = client.tasks.get(TASK_UUID)
        waited = client.tasks.wait(TASK_UUID, poll_timeout=5.0)
        count = client.tasks.acknowledge([17])

    assert isinstance(listed, PagedResult)
    assert listed.results[0].task_id == TASK_UUID
    assert fake.requests[0].url.params["acknowledged"] == "false"
    assert task.id == 17
    assert waited.status == TaskStatus.SUCCESS
    assert count == 1


def test_sync_tasks_wait_raises_with_task_and_task_id() -> None:
    failed = task_json(status="FAILURE", result=DUPLICATE_RESULT, related_document=None)
    fake = FakePaperless({TASKS_PATH: FakePaperless.seq([failed], [pending()])})
    with fake.sync_client(poll_interval=FAST) as client:
        with pytest.raises(UploadError) as upload_err:
            client.tasks.wait(TASK_UUID)
        with pytest.raises(TaskTimeoutError) as timeout_err:
            client.tasks.wait(TASK_UUID, poll_timeout=0.01)

    assert upload_err.value.task is not None
    assert upload_err.value.task.result == DUPLICATE_RESULT
    assert timeout_err.value.task_id == TASK_UUID


# --- compatibility ----------------------------------------------------------------


def test_task_models_importable_from_all_public_paths() -> None:
    for module in (easypaperless, models, documents_models):
        assert module.Task is tasks_models.Task
        assert module.TaskStatus is tasks_models.TaskStatus


def test_exception_constructors_stay_backward_compatible() -> None:
    assert str(UploadError("boom")) == "boom"
    assert UploadError("boom").task is None
    assert UploadError("boom", 400).status_code == 400
    err = TaskTimeoutError("late")
    assert str(err) == "late"
    assert err.task_id is None and err.timeout is None and err.status_code is None


def test_task_accepts_integer_related_document_and_ignores_unknown_fields() -> None:
    task = Task.model_validate(task_json(related_document=42, duplicate_documents=[]))
    assert task.related_document == "42"


# --- unknown status values -------------------------------------------------------


def test_task_keeps_unknown_status_string_instead_of_raising() -> None:
    task = Task.model_validate(task_json(status="RECEIVED"))
    assert task.status == "RECEIVED"
    assert not isinstance(task.status, TaskStatus)


def test_task_still_parses_known_status_as_enum() -> None:
    task = Task.model_validate(task_json(status="FAILURE"))
    assert task.status is TaskStatus.FAILURE


async def test_list_returns_tasks_with_unknown_status() -> None:
    fake = FakePaperless({TASKS_PATH: [task_json(status="SOMETHING_NEW")]})
    async with fake.async_client() as client:
        result = await client.tasks.list()

    assert result.results[0].status == "SOMETHING_NEW"


async def test_wait_treats_unknown_status_as_not_finished() -> None:
    fake = FakePaperless(
        {TASKS_PATH: FakePaperless.seq([pending(status="RECEIVED")], [task_json()])}
    )
    async with fake.async_client() as client:
        task = await client.tasks.wait(TASK_UUID, poll_interval=FAST)

    assert task.status is TaskStatus.SUCCESS
    assert len(fake.requests) == 2


async def test_wait_with_only_unknown_status_times_out() -> None:
    fake = FakePaperless({TASKS_PATH: [pending(status="RECEIVED")]})
    async with fake.async_client() as client:
        with pytest.raises(TaskTimeoutError) as exc_info:
            await client.tasks.wait(TASK_UUID, poll_interval=FAST, poll_timeout=0.05)

    assert exc_info.value.task_id == TASK_UUID
