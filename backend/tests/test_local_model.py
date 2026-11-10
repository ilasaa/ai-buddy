import os

import numpy as np
import pytest

from app.services.embeddings import provider


@pytest.mark.local_model
@pytest.mark.skipif(
    os.environ.get("RUN_LOCAL_MODEL_TEST") != "1",
    reason="Явный запуск: RUN_LOCAL_MODEL_TEST=1 pytest -m local_model",
)
def test_real_local_e5():
    documents = provider.encode(
        [
            "Чтобы получить доступ к GitLab, подготовьте заявку на права к репозиторию.",
            "Обед можно разогреть на кухне.",
        ],
        "passage",
    )
    query = provider.encode(["Где запросить права на репозиторий?"], "query")[0]
    vectors = np.asarray(documents)
    assert vectors.shape == (2, 384)
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1, atol=1e-5)
    scores = vectors @ np.asarray(query)
    assert scores[0] > scores[1]
