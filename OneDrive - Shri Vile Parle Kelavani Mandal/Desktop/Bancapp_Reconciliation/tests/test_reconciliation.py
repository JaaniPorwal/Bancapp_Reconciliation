from src.reconciliation import normalize_reference

def test_1n_normalization():
    assert normalize_reference("PART SETTLEMENT PRMAY48951595-P2") == "PRMAY48951595"
    assert normalize_reference("PRMAY48951595") == "PRMAY48951595"