from coach.retriever import Retriever, load_knowledge, load_past_games, tokenize


def test_tokenize_drops_stopwords_and_plurals():
    assert tokenize("The guesses are in the range") == ["guess", "range"]
    assert tokenize("hints and numbers") == ["hint", "number"]
    assert "the" not in tokenize("the secret")


def test_knowledge_files_load_as_sections():
    docs = load_knowledge()
    ids = {d.doc_id for d in docs}
    assert "opening_moves#opening-guess" in ids
    assert "binary_search#midpoint-strategy" in ids
    assert all(d.source == "knowledge" for d in docs)


def test_past_games_load_for_every_difficulty():
    docs = load_past_games()
    assert {d.fields["difficulty"] for d in docs} == {"Easy", "Normal", "Hard"}


def test_missing_past_games_file_gives_empty_list(tmp_path):
    assert load_past_games(tmp_path / "nope.json") == []


def test_search_ranks_the_matching_section_first():
    retriever = Retriever.default()
    top = retriever.search("opening first guess start midpoint binary search", k=1, source="knowledge")[0]
    assert top.doc.doc_id == "opening_moves#opening-guess"


def test_search_with_no_matching_terms_returns_nothing():
    assert Retriever.default().search("pizza tomato recipe") == []


def test_search_can_filter_by_source():
    hits = Retriever.default().search("Hard difficulty simulated games", k=3, source="history")
    assert hits and all(h.doc.source == "history" for h in hits)
    assert hits[0].doc.fields["difficulty"] == "Hard"


def test_empty_corpus_and_empty_query_are_safe():
    assert Retriever([]).search("anything") == []
    assert Retriever.default().search("") == []
