# SKILL.md — Pipeline State (anti-drift anchor)

## Active Branch
`claude/enhance-ooda-loop-pecnY`

## Architecture
```
ooda_loop.py  →  observe.py → orient.py → decide.py → act.py
                                                          ↓
                                                    produce.py
                                                          ↓
                                          TTSEngine (ElevenLabs + edge_tts fallback)
                                          WhisperEngine (local, word-level sync)
                                          SubtitleEngine (ASS + animations + emoji)
                                          FootageEngine (yt_dlp cached)
                                          Renderer (FFmpeg loudnorm CRF19)
```

## Critical Fixes (never regress)
| Bug | Fix | Test |
|-----|-----|------|
| FFmpeg 8.x misparses `C:` as option separator in `ass=` filter | `_safe_path()` uses relative path | `TestSafePath::test_relative_path_no_colon` |
| ElevenLabs 401 crashes pipeline | `TTSEngine` falls back to `edge_tts` | `TestTTSCache::test_cache_hit_copies_file` |
| `audio_base64` AttributeError (SDK v2.42) | Use `audio_base_64` (underscore before 64) | covered in TTSEngine |
| `sys.exit()` in thread silently swallows errors | `_tts_job` catches + checks `audio_path.exists()` after join | integration flow |

## TDD Protocol
- Tests: `tests/test_produce.py` (39 tests, all green)
- Log: `.claude/test_logs.json`
- Run: `python -m pytest tests/ -v`
- Rule: no new feature ships without a corresponding test

## Env Vars Required
```
ELEVENLABS_API_KEY   # TTS (falls back to edge_tts if missing)
ANTHROPIC_API_KEY    # Orient phase Claude scoring
REDDIT_CLIENT_ID     # Observe phase scraping
REDDIT_CLIENT_SECRET
```

## Run Commands
```
py produce.py                    # single video (default story)
py ooda_loop.py                  # one OODA cycle
py ooda_loop.py --daemon         # autonomous loop (60min intervals)
py ooda_loop.py --produce        # force-produce ready queue items
py ooda_loop.py --report         # queue + performance stats
py check_env.py                  # validate all API keys
python -m pytest tests/ -v       # run test suite
```
