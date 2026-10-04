import pytest
from pydantic import ValidationError

from miner.clone.models import Repository


@pytest.mark.parametrize("value", ["", "   ", 123, None])
def test_model_validation(value):
    with pytest.raises(ValidationError):
        Repository(full_name=value, clone_url="https://github.com/org/a.git")
