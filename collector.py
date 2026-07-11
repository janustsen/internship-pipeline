from __future__ import annotations

import argparse
import logging
import subprocess
from datetime import date
from pathlib import Path
from typing import Callable, Iterable

from config import Config, ConfigError, required_env_for_sources
from coverage_report import CoverageReport
from filters import candidate_category, firm_match, is_relevant_posting
from handoff import commit_and_push, write_handoff
from http_client import RetryingHttpClient
from models import Candidate, RawPosting, raw_posting_from_mapping
from sources import adzuna, ats, handshake, linkedin, serper
from store import InternshipStore
from target_firms import all_source_tokens


LOGGER = logging.getLogger("internship_collector")
SOURCE_NAMES = ("ats", "adzuna", "serper", "linkedin", "handshake")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect internship postings into a git bridge.")
    parser.add_argument("--dry-run", action="store_true", help="do not mutate the lifetime DB")
    parser.add_argument("--no-push", action="store_true", help="write artifact but skip git push")
    parser.add_argument("--source", choices=SOURCE_NAMES, action="append", help="run one source")
    parser.add_argument("--since", help="source-side lower bound date, YYYY-MM-DD")
    parser.add_argument("--db", default="seen_internships.db")
    parser.add_argument("--artifact", default="todays_candidates.json")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--strict-env", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = build_parser().parse_args(argv)
    try:
        result = run_collector(args)
    except ConfigError as exc:
        LOGGER.error("%s", exc)
        return 2
    for line in result.coverage.lines():
        LOGGER.info(line)
    return 0


class CollectorResult:
    def __init__(
        self,
        *,
        raw_candidates: list[Candidate],
        new_candidates: list[Candidate],
        coverage: CoverageReport,
        artifact: dict[str, object],
    ) -> None:
        self.raw_candidates = raw_candidates
        self.new_candidates = new_candidates
        self.coverage = coverage
        self.artifact = artifact


def run_collector(
    args: argparse.Namespace,
    *,
    fetchers: dict[str, Callable[[], Iterable[RawPosting | dict]]] | None = None,
    store: InternshipStore | None = None,
    http: RetryingHttpClient | None = None,
    git_runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> CollectorResult:
    selected_sources = list(dict.fromkeys(args.source or SOURCE_NAMES))
    required = required_env_for_sources(selected_sources) if fetchers is None else ()
    config = Config.from_env(
        env_path=args.env_file,
        required=required,
        require_existing_env_file=args.strict_env,
    )
    client = http or RetryingHttpClient()
    owns_store = store is None
    active_store = store or InternshipStore(args.db)
    coverage = CoverageReport()
    try:
        source_fetchers = fetchers or default_fetchers(
            selected_sources,
            config=config,
            store=active_store,
            http=client,
            since=args.since,
        )
        source_fetchers = {
            name: fetcher for name, fetcher in source_fetchers.items() if name in selected_sources
        }
        filtered = collect_from_sources(source_fetchers, coverage=coverage)
        deduped = active_store.dedupe(filtered, dry_run=args.dry_run)
        new_links = {candidate.link for candidate in deduped.new}
        for candidate in filtered:
            source_coverage = coverage.source(candidate.source)
            if candidate.link in new_links:
                source_coverage.keep()
            else:
                source_coverage.drop("duplicate")
        coverage.assert_no_silent_drops()
        artifact = write_handoff(deduped.new, path=args.artifact, run_date=date.today().isoformat())
        commit_and_push(args.artifact, no_push=args.no_push, dry_run=args.dry_run, runner=git_runner)
        return CollectorResult(
            raw_candidates=filtered,
            new_candidates=deduped.new,
            coverage=coverage,
            artifact=artifact,
        )
    finally:
        if owns_store:
            active_store.close()


def default_fetchers(
    selected_sources: list[str],
    *,
    config: Config,
    store: InternshipStore,
    http: RetryingHttpClient,
    since: str | None,
) -> dict[str, Callable[[], Iterable[RawPosting]]]:
    fetchers: dict[str, Callable[[], Iterable[RawPosting]]] = {}
    if "ats" in selected_sources:
        tokens = [*all_source_tokens(), *store.active_tokens()]
        fetchers["ats"] = lambda: ats.fetch_ats_tokens(tokens, http=http)
    if "adzuna" in selected_sources:
        env = config.require("ADZUNA_APP_ID", "ADZUNA_APP_KEY")
        fetchers["adzuna"] = lambda: adzuna.fetch_adzuna(
            app_id=env["ADZUNA_APP_ID"],
            app_key=env["ADZUNA_APP_KEY"],
            http=http,
            since=since,
        )
    if "serper" in selected_sources:
        env = config.require("SERPER_API_KEY")
        fetchers["serper"] = lambda: serper.fetch_serper(api_key=env["SERPER_API_KEY"], http=http)
    if "linkedin" in selected_sources:
        env = config.require("APIFY_TOKEN", "LINKEDIN_APIFY_ACTOR_ID")
        fetchers["linkedin"] = lambda: linkedin.fetch_linkedin(
            apify_token=env["APIFY_TOKEN"],
            actor_id=env["LINKEDIN_APIFY_ACTOR_ID"],
        )
    if "handshake" in selected_sources:
        script = config.get("HANDSHAKE_SCRAPER_PATH", "handshake_scraper.py")
        fetchers["handshake"] = lambda: handshake.fetch_handshake(script_path=script)
    return fetchers


def collect_from_sources(
    fetchers: dict[str, Callable[[], Iterable[RawPosting | dict]]],
    *,
    coverage: CoverageReport | None = None,
) -> list[Candidate]:
    report = coverage or CoverageReport()
    candidates: list[Candidate] = []
    for source, fetcher in fetchers.items():
        source_coverage = report.source(source)
        try:
            raw_items = list(fetcher())
        except Exception as exc:  # one dead source must not abort the run
            source_coverage.errors.append(str(exc))
            LOGGER.exception("source %s failed; continuing", source)
            continue
        source_coverage.raw += len(raw_items)
        for item in raw_items:
            try:
                posting = coerce_posting(item, source)
            except ValueError:
                source_coverage.drop("malformed")
                continue
            matched = firm_match(posting.company)
            if matched is None:
                source_coverage.drop("non_allowlisted")
                continue
            if not is_relevant_posting(posting):
                source_coverage.drop("irrelevant")
                continue
            candidates.append(
                Candidate(
                    tier_hint=matched["tier"],
                    category=candidate_category(posting),
                    company=matched["canonical"],
                    title=posting.title,
                    location=posting.location,
                    link=posting.link,
                    source=posting.source or source,
                    posted=posting.posted,
                )
            )
    return candidates


def coerce_posting(item: RawPosting | dict, source: str) -> RawPosting:
    posting = item if isinstance(item, RawPosting) else raw_posting_from_mapping(item, source)
    if not (posting.company and posting.title and posting.link):
        raise ValueError("malformed posting")
    return posting


if __name__ == "__main__":
    raise SystemExit(main())
