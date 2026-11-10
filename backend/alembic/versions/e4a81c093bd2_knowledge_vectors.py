"""Knowledge documents with pgvector. Requires installed PostgreSQL extension files."""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "e4a81c093bd2"
down_revision = "d39f72b8a012"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(250), nullable=False),
        sa.Column("source", sa.String(500), unique=True, nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("embedding_model", sa.String(200), nullable=False),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="RESTRICT")),
        sa.Column("is_public", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "(is_public AND team_id IS NULL) OR (NOT is_public AND team_id IS NOT NULL)",
            name="ck_knowledge_scope",
        ),
    )
    op.create_index("ix_knowledge_documents_team_id", "knowledge_documents", ["team_id"])
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "document_id",
            sa.Integer(),
            sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_document_chunk"),
        sa.CheckConstraint("chunk_index >= 0", name="ck_chunk_index"),
    )
    op.create_index("ix_knowledge_chunks_document_id", "knowledge_chunks", ["document_id"])
    # Exact cosine search: small MVP corpus, ACL filtering before LIMIT. HNSW can be
    # introduced after benchmarking recall under team filters on a larger corpus.


def downgrade():
    op.drop_table("knowledge_chunks")
    op.drop_table("knowledge_documents")
    # Keep the shared extension installed.
