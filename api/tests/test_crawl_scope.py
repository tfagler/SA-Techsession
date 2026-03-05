from app.services.ingest import _is_in_parent_tree


def test_parent_tree_restricts_to_same_domain_and_subtree():
    start = 'https://example.com/docs/guide/index.html'
    assert _is_in_parent_tree(start, 'https://example.com/docs/guide/intro.html')
    assert _is_in_parent_tree(start, 'https://example.com/docs/guide/sub/topic.html')
    assert not _is_in_parent_tree(start, 'https://example.com/docs/other/page.html')
    assert not _is_in_parent_tree(start, 'https://other.com/docs/guide/intro.html')


def test_parent_tree_root_allows_same_domain_paths():
    start = 'https://example.com/'
    assert _is_in_parent_tree(start, 'https://example.com/a')
    assert _is_in_parent_tree(start, 'https://example.com/a/b/c')
