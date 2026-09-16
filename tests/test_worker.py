from unittest.mock import patch, MagicMock

from megaqueue.worker import _poll_once


@patch("megaqueue.worker.sync")
def test_poll_once_drives_sync_in_order(mock_sync):
    """A single poll tick calls submit_pending, then sync_active, then integrity_sweep."""
    mock_sync.sync_active.return_value = {1, 2}
    manager = MagicMock()
    manager.status.return_value = {"downloads": [{"url": "x"}]}

    _poll_once(manager)

    mock_sync.submit_pending.assert_called_once_with(manager)
    mock_sync.sync_active.assert_called_once_with(manager, [{"url": "x"}])
    mock_sync.integrity_sweep.assert_called_once_with({1, 2})


@patch("megaqueue.worker.sync")
def test_poll_once_swallows_status_error(mock_sync):
    """If manager.status() raises, the tick logs and returns without calling sync_active."""
    manager = MagicMock()
    manager.status.side_effect = ConnectionError("download engine error")

    _poll_once(manager)

    mock_sync.submit_pending.assert_called_once()
    mock_sync.sync_active.assert_not_called()
    mock_sync.integrity_sweep.assert_not_called()
