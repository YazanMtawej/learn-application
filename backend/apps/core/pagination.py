from rest_framework.pagination import CursorPagination


class DefaultCursorPagination(CursorPagination):
    """
    Cursor-based pagination foundation per PHASE_7_API_SERVICE_CONTRACTS.md §1
    ("Cursor-based لأي List Endpoint قابل للنمو غير المحدود"). Not yet consumed
    by any TASK 1 endpoint; provided as reusable DRF configuration for
    subsequent list-type endpoints.
    """

    page_size = 20
    ordering = "-created_at"
    cursor_query_param = "cursor"
    page_size_query_param = "page_size"
    max_page_size = 100