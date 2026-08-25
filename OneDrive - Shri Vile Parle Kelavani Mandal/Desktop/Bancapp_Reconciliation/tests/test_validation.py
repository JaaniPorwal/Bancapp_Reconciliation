from src.validation import validate_all_inputs


def test_all_input_files_can_be_read():
    dataframes, report = validate_all_inputs("data")

    assert "internal_may" in dataframes
    assert "bank_may" in dataframes
    assert "internal_jun" in dataframes
    assert "bank_jun" in dataframes