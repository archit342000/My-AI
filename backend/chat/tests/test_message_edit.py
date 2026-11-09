import json

import pytest

from backend.chat.message_edit import merge_edited_user_content

NOTE = "\n\n[System Note: The user has attached the following files. Use the `document_agent` tool with the provided file_id to read their contents if needed:\n- a.pdf (ID: f1)]"


def test_plain_content_is_replaced():
    assert merge_edited_user_content("old text", "new text") == "new text"


def test_plain_content_keeps_the_attachment_note_when_the_edit_drops_it():
    assert merge_edited_user_content("old text" + NOTE, "new text") == "new text" + NOTE


def test_edit_that_already_carries_the_note_is_not_duplicated():
    edited = "new text" + NOTE
    assert merge_edited_user_content("old text" + NOTE, edited) == edited


def test_multimodal_content_keeps_images_and_replaces_the_text():
    old = json.dumps([
        {"type": "text", "text": "look" + NOTE},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAA"}},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,BBB"}},
    ])
    merged = json.loads(merge_edited_user_content(old, "look again"))
    assert merged[0] == {"type": "text", "text": "look again" + NOTE}
    assert [p["image_url"]["url"] for p in merged[1:]] == ["data:image/png;base64,AAA", "data:image/png;base64,BBB"]


def test_multimodal_edit_that_carries_the_note_is_not_duplicated():
    old = json.dumps([{"type": "text", "text": "x" + NOTE}, {"type": "image_url", "image_url": {"url": "u"}}])
    merged = json.loads(merge_edited_user_content(old, "y" + NOTE))
    assert merged[0]["text"] == "y" + NOTE
    assert merged[0]["text"].count("[System Note:") == 1


def test_multimodal_content_without_a_text_part_gets_one():
    old = json.dumps([{"type": "image_url", "image_url": {"url": "u"}}])
    merged = json.loads(merge_edited_user_content(old, "caption"))
    assert merged == [{"type": "text", "text": "caption"}, {"type": "image_url", "image_url": {"url": "u"}}]


def test_content_that_is_not_a_list_of_objects_is_plain_text():
    assert merge_edited_user_content("not json", "new") == "new"
    assert merge_edited_user_content('["a", "b"]', "new") == "new"
    assert merge_edited_user_content('{"type": "text"}', "new") == "new"
    assert merge_edited_user_content("", "new") == "new"


@pytest.mark.parametrize("old", ["[]", '[{"a": 1}]', '[{"type": "other"}]', '[{"type": 5}]', '[{"type": "text", "text": "x"}, 3]'])
def test_plain_text_shaped_like_json_is_not_treated_as_multimodal(old):
    assert merge_edited_user_content(old, "hello") == "hello"


def test_none_stored_content_is_plain_text():
    assert merge_edited_user_content(None, "hello") == "hello"


def test_image_before_the_text_part_keeps_the_order():
    old = json.dumps([
        {"type": "image_url", "image_url": {"url": "u1"}},
        {"type": "text", "text": "look" + NOTE},
        {"type": "image_url", "image_url": {"url": "u2"}},
    ])
    merged = json.loads(merge_edited_user_content(old, "look again"))
    assert [p["type"] for p in merged] == ["image_url", "text", "image_url"]
    assert merged[1]["text"] == "look again" + NOTE


def test_only_the_last_note_block_is_treated_as_the_attachment_note():
    typed = "see this\n\n[System Note: typed by the user]"
    old = typed + NOTE
    assert merge_edited_user_content(old, "new") == "new" + NOTE


def test_a_typed_system_note_in_the_draft_does_not_stop_the_router_note_being_kept():
    draft = "see\n\n[System Note: typed by the user]"
    assert merge_edited_user_content("old" + NOTE, draft) == draft + NOTE


def test_a_typed_system_note_in_the_stored_text_is_not_mistaken_for_the_router_note():
    stored = "typed only\n\n[System Note: typed by the user]"
    assert merge_edited_user_content(stored, "new") == "new"
