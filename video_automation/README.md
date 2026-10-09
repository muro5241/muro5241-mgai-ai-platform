# MGAI video automation

A standalone, opt-in local/cloud video rendering module. Does not modify the FastAPI service, deploy to Render, or publish to TikTok.

Requirements: Python 3.11+, FFmpeg with libx264 and AAC, internet access for edge-tts.

```sh
python -m pip install -r video_automation/requirements.txt
python video_automation/produce.py --count 10
```

Videos and manifest are written to `video_automation/output/`. Set `--count 50` for 50 videos. Charts are illustrative, not live market data. The script rotates a fixed educational topic bank; it does not yet generate fresh AI topics. TikTok OAuth, publication, cloud scheduling and 24/7 uptime are NOT configured.
