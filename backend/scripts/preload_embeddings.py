from app.core.config import settings
from app.services.embeddings import load_model

if __name__ == "__main__":
    model = load_model(settings.embedding_model, False)
    print(
        f"Модель готова: {settings.embedding_model}; размерность: {model.get_sentence_embedding_dimension()}"
    )
