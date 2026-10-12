from pathlib import Path

from core.phone_export import copy_final_video_to_phone


def test_phone_export_copies_and_verifies_final_mp4(tmp_path):
    source = tmp_path / "rendered_final.mp4"
    payload = b"rendered-mp4-test-payload" * 1000
    source.write_bytes(payload)
    phone_home = tmp_path / "termux-home"

    copied = copy_final_video_to_phone(
        {"output_path": str(source)},
        tmp_path / "outputs",
        home_dir=phone_home,
    )

    movies = phone_home / "storage" / "shared" / "Movies" / "AutoFaceless" / source.name
    dcim = phone_home / "storage" / "shared" / "DCIM" / "AutoFaceless" / source.name
    assert copied == str(movies)
    assert movies.is_file() and movies.read_bytes() == payload
    assert dcim.is_file() and dcim.read_bytes() == payload
    assert movies.stat().st_size == source.stat().st_size
    assert dcim.stat().st_size == source.stat().st_size
    assert not list(phone_home.rglob("*.part"))


def test_phone_export_does_not_claim_success_without_a_final_file(tmp_path):
    copied = copy_final_video_to_phone(
        {"output_path": str(tmp_path / "missing.mp4")},
        tmp_path / "outputs",
        home_dir=tmp_path / "termux-home",
    )
    assert copied is None
