from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

class Novel(Base):
    __tablename__ = "novels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title_raw: Mapped[str] = mapped_column(String(255), nullable=False)
    title_rough: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    author: Mapped[Optional[str]] = mapped_column(String(255), default="Unknown Author")
    cover_url: Mapped[Optional[str]] = mapped_column(Text, default="")
    genres: Mapped[Optional[str]] = mapped_column(String(255), default="")
    context_profile: Mapped[Optional[str]] = mapped_column(String(50), default="")
    status: Mapped[str] = mapped_column(String(50), default="Ongoing")
    source_url: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    chapters: Mapped[List["Chapter"]] = relationship("Chapter", back_populates="novel", cascade="all, delete-orphan")


class Chapter(Base):
    __tablename__ = "chapters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    novel_id: Mapped[int] = mapped_column(Integer, ForeignKey("novels.id", ondelete="CASCADE"), nullable=False)
    chapter_no: Mapped[int] = mapped_column(Integer, nullable=False)
    title_raw: Mapped[str] = mapped_column(String(255), nullable=False)
    title_rough: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    url: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Overview status of chapter ('WAIT', 'CRAWLED', 'TRANSLATING', 'DONE', 'FAILED')
    status: Mapped[str] = mapped_column(String(50), default="WAIT", index=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, default="")
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    novel: Mapped["Novel"] = relationship("Novel", back_populates="chapters")
    versions: Mapped[List["ChapterVersion"]] = relationship("ChapterVersion", back_populates="chapter", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_novel_chapter_no", "novel_id", "chapter_no", unique=True),
    )


class ChapterVersion(Base):
    """
    Bảng quản lý các phiên bản nội dung (RAW, GG, GEMINI, GPT, CLAUDE, FINAL).
    Chỉ lưu metadata đường dẫn file đĩa, không lưu nội dung text lớn trong DB!
    """
    __tablename__ = "chapter_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chapter_id: Mapped[int] = mapped_column(Integer, ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False)
    
    # Version Type: 'RAW', 'GG', 'GEMINI', 'GPT', 'CLAUDE', 'FINAL'
    version_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    
    # Engine Used: 'crawler', 'google', 'gemini-3.6-flash', 'openai-gpt4o', 'manual'
    engine: Mapped[str] = mapped_column(String(100), default="unknown")
    
    # File Path on disk (e.g. Output/ggDich/Tên_Truyện/000001.txt)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Nội dung text chương lưu trực tiếp trong DB để tối ưu truy xuất
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Status: 'COMPLETED', 'FAILED'
    status: Mapped[str] = mapped_column(String(50), default="COMPLETED")
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationship back to Chapter
    chapter: Mapped["Chapter"] = relationship("Chapter", back_populates="versions")

    __table_args__ = (
        Index("idx_chapter_version", "chapter_id", "version_type", unique=True),
    )


class PhraseDictionary(Base):
    """
    Từ điển từ ghép offline dùng chung.
    chinese_phrase -> vietnamese_phrase
    """
    __tablename__ = "phrase_dictionary"

    chinese_phrase: Mapped[str] = mapped_column(String(255), primary_key=True)
    vietnamese_phrase: Mapped[str] = mapped_column(String(255), nullable=False)


class NamesDictionary(Base):
    """
    Từ điển tên nhân vật / thuật ngữ riêng (Novel-specific & Global)
    """
    __tablename__ = "names_dictionary"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    novel_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("novels.id", ondelete="CASCADE"), nullable=True)
    chinese_name: Mapped[str] = mapped_column(String(255), nullable=False)
    vietnamese_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Relationships
    novel: Mapped[Optional[Novel]] = relationship("Novel")

    __table_args__ = (
        Index("idx_names_lookup", "chinese_name", "novel_id"),
    )


class NovelEntity(Base):
    """
    Bảng quản lý thực thể truyện phân loại và định danh:
    - NAME: Tên Nhân Vật
    - PLACE: Địa Danh
    - SECT: Tông Môn / Phái / Tập Đoàn
    - ITEM: Vật Phẩm / Bảo Vật / Thiết Bị
    - SKILL: Chiêu Thức / Võ Kỹ / Công Pháp
    - OTHER: Từ Ngữ Khác
    """
    __tablename__ = "novel_entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    novel_id: Mapped[int] = mapped_column(Integer, ForeignKey("novels.id", ondelete="CASCADE"), nullable=False)
    chinese_name: Mapped[str] = mapped_column(String(255), nullable=False)
    rough_translation: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Phân loại: 'NAME', 'PLACE', 'SECT', 'ITEM', 'SKILL', 'OTHER' (Cũ: 'PERSON', 'LOCATION', 'SECT_SKILL')
    entity_type: Mapped[str] = mapped_column(String(50), default="NAME")
    frequency_count: Mapped[int] = mapped_column(Integer, default=1)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_entity_lookup", "novel_id", "chinese_name", unique=True),
    )


class ChapterEntityLink(Base):
    """
    Bảng liên kết Thực thể (NovelEntity) theo từng Chương cụ thể (chapter_id).
    Giúp truy xuất siêu tốc từ điển cho từng chương mà không cần quét lại toàn bộ CSDL.
    """
    __tablename__ = "chapter_entity_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chapter_id: Mapped[int] = mapped_column(Integer, ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, ForeignKey("novel_entities.id", ondelete="CASCADE"), nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_chap_ent_link", "chapter_id", "entity_id", unique=True),
    )


class ChapterCorrection(Base):
    """
    Bảng quản lý sửa lỗi dịch GG phát hiện lọt lưới THEO TỪNG CHƯƠNG.
    Chỉ dùng riêng cho luồng biên tập CONTEXTT của chương đó.
    """
    __tablename__ = "chapter_corrections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chapter_id: Mapped[int] = mapped_column(Integer, ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False)
    wrong_text: Mapped[str] = mapped_column(String(255), nullable=False)
    correct_text: Mapped[str] = mapped_column(String(255), nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_chapter_corr_lookup", "chapter_id", "wrong_text"),
    )


class Setting(Base):
    """
    Bảng quản lý cấu hình hệ thống động (Settings) lưu trong DB.
    """
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)


class UnblockDictionary(Base):
    """
    Từ điển giấu từ nhạy cảm (Unblock).
    Lưu trữ các từ ngữ nhạy cảm (Tiếng Việt và Tiếng Trung) để mã hóa trước khi đưa vào LLM.
    """
    __tablename__ = "unblock_dictionary"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    word: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="scene")
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TTSChunk(Base):
    """
    Bảng quản lý phân mảnh văn bản để chạy Edge-TTS Audiobook quy mô lớn.
    """
    __tablename__ = "tts_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    novel_id: Mapped[int] = mapped_column(Integer, ForeignKey("novels.id", ondelete="CASCADE"), nullable=False)
    volume_no: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_id: Mapped[int] = mapped_column(Integer, nullable=False)
    text_content: Mapped[str] = mapped_column(Text, nullable=False)
    
    # status: 'PENDING', 'PROCESSING', 'DONE', 'FAILED'
    status: Mapped[str] = mapped_column(String(50), default="PENDING", index=True)
    audio_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_novel_volume_chunk", "novel_id", "volume_no", "chunk_id", unique=True),
    )
