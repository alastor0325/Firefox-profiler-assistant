# tests/test_downloader.py

import pytest
from profiler_assistant.downloader import get_profile_from_url

def test_get_profile_from_url_success(mocker):
    """
    Tests the successful download and token extraction from a share URL.
    """
    # Mock the first GET request to the short URL
    mock_response_redirect = mocker.Mock()
    mock_response_redirect.status_code = 200
    mock_response_redirect.url = "https://profiler.firefox.com/public/some_long_token/calltree/?..."
    
    # Mock the final GET request to the storage URL
    mock_response_download = mocker.MagicMock()

    # FIX: Make the mock compatible with the 'with' statement
    mock_response_download.__enter__.return_value = mock_response_download
    mock_response_download.__exit__.return_value = None
    mock_response_download.status_code = 200
    mock_response_download.headers = {'content-length': '12345'}
    mock_response_download.iter_content.return_value = [b'{"meta":{}}']

    # Patch requests.get to return our mock responses in order
    mocker.patch('requests.get', side_effect=[mock_response_redirect, mock_response_download])
    
    # Mock open to avoid actual file I/O
    mocker.patch('builtins.open', mocker.mock_open())

    short_url = "https://share.firefox.dev/3HkKTjj"
    temp_file_path = get_profile_from_url(short_url)

    assert "profile_some_long_token.json" in temp_file_path

def test_get_profile_from_url_bad_redirect(mocker):
    """
    Tests that an error is raised if the resolved URL is not in the expected format.
    """
    mock_response_redirect = mocker.Mock()
    mock_response_redirect.status_code = 200
    mock_response_redirect.url = "https://some_other_website.com/page"
    mocker.patch('requests.get', return_value=mock_response_redirect)

    with pytest.raises(ValueError, match="Could not find a valid token"):
        get_profile_from_url("https://share.firefox.dev/3HkKTjj")