from daps_webui import db


class FileCache(db.Model):
    __tablename__ = "file_cache"
    file_path = db.Column(db.String, primary_key=True)
    file_name = db.Column(db.String)
    status = db.Column(db.String, nullable=True, default=None)
    has_episodes = db.Column(db.Boolean, nullable=True, default=None)
    media_type = db.Column(db.String)
    file_hash = db.Column(db.String, unique=True)
    original_file_hash = db.Column(db.String, unique=True)
    source_path = db.Column(db.String)
    border_replaced = db.Column(db.Boolean, default=False)
    uploaded_to_plex = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())


class UnmatchedMovies(db.Model):
    __tablename__ = "unmatched_movies"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String, unique=True)


class UnmatchedCollections(db.Model):
    __tablename__ = "unmatched_collections"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String, unique=True)


class UnmatchedShows(db.Model):
    __tablename__ = "unmatched_shows"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String, unique=True)
    main_poster_missing = db.Column(db.Boolean, default=None)
    seasons = db.relationship(
        "UnmatchedSeasons", backref="show", cascade="all, delete-orphan", lazy=True
    )


class UnmatchedSeasons(db.Model):
    __tablename__ = "unmatched_seasons"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    show_id = db.Column(
        db.Integer,
        db.ForeignKey("unmatched_shows.id", ondelete="CASCADE"),
        nullable=False,
    )
    season = db.Column(db.String)
    __table_args__ = (
        db.UniqueConstraint("show_id", "season", name="unique_show_season"),
    )


class UnmatchedStats(db.Model):
    __tablename__ = "unmatched_stats"
    id = db.Column(
        db.Integer,
        primary_key=True,
    )
    total_movies = db.Column(db.Integer, default=0)
    total_series = db.Column(db.Integer, default=0)
    total_seasons = db.Column(db.Integer, default=0)
    total_collections = db.Column(db.Integer, default=0)
    unmatched_movies = db.Column(db.Integer, default=0)
    unmatched_series = db.Column(db.Integer, default=0)
    unmatched_seasons = db.Column(db.Integer, default=0)
    unmatched_collections = db.Column(db.Integer, default=0)
