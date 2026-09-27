import pandas as pd
import pytest

from pointmap.classify import classify_point
from pointmap.ingest import to_records
from pointmap.rules import load_rules
from pointmap.tokens import parse_name


@pytest.fixture(scope="session")
def rules():
    return load_rules()


@pytest.fixture(scope="session")
def classify(rules):
    """Classify one point from its name and metadata, no files involved."""
    def _classify(name, object_type="", units="", description="", site="TEST"):
        frame = pd.DataFrame([{"point_name": name, "object_type": object_type,
                               "units": units, "description": description}])
        record = to_records(frame, rules)[0]
        return classify_point(site, record, parse_name(record.point_name, rules), rules)
    return _classify
