@echo off
title Granite CRM — Cloudflare Tunnel
echo Starting Cloudflare Tunnel for track.greenhill-tours.store...
"%~dp0cloudflared.exe" tunnel run
pause
