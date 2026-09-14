"""Read the canonical daily source without exporting its private machine data."""

import importlib.util
import os
import sys
from pathlib import Path


def resolve_bundle_reading(path, *, dashboard_root=None, market_watch_root=None, bundle_root=None):
    dashboard = Path(dashboard_root or os.environ.get('GUANCHAO_DASHBOARD_ROOT') or
                     Path(__file__).resolve().parents[2] / 'live-dashboard').resolve()
    market_watch = Path(market_watch_root or os.environ.get('MARKET_WATCH_ROOT') or
                        dashboard.parent / 'Market_Watch').resolve()
    package = sys.modules.get('scripts')
    if package is not None and all(Path(item).resolve() != dashboard / 'scripts'
                                   for item in getattr(package, '__path__', [])):
        raise ValueError('daily_bundle_reader_root_conflict')
    if str(dashboard) not in sys.path:
        sys.path.insert(0, str(dashboard))
    spec = importlib.util.spec_from_file_location(
        '_portal_daily_review_source', dashboard / 'scripts/review_source.py')
    if spec is None or spec.loader is None:
        raise ValueError('daily_bundle_reader_missing')
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    return reader.resolve_review_input(
        path, dashboard_root=dashboard, market_watch_root=market_watch,
        bundle_root=bundle_root or os.environ.get('YM_DAILY_BUNDLE_ROOT'))
