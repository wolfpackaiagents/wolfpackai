"""Tests for model resolution (get_model, get_model_from_env)."""

from __future__ import annotations

import os

import pytest

from wolfpack.models.utils import _build, get_model, get_model_from_env


def test_get_model_google_from_prefix(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    model = get_model("google:gemini-2.0-flash")
    assert model.provider == "google"
    assert model.model_id == "gemini-2.0-flash"


def test_get_model_google_auto_detect(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    model = get_model("gemini-2.0-flash")
    assert model.provider == "google"


def test_get_model_google_infer(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    model = get_model("gemini-2.5-pro-exp-03-25")
    assert model.provider == "google"


def test_get_model_from_env_google(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    model = get_model_from_env()
    assert model.provider == "google"
    assert model.model_id == "gemini-2.0-flash"


def test_build_google(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    model = _build("google", "gemini-2.0-flash")
    assert model.provider == "google"
    assert model.model_id == "gemini-2.0-flash"


def test_get_model_from_env_priority(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("GOOGLE_API_KEY", "goog-test")
    model = get_model_from_env()
    assert model.provider == "openai"


def test_get_model_from_env_preferred(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    model = get_model_from_env(preferred="google:gemini-2.5-pro-exp-03-25")
    assert model.provider == "google"
    assert model.model_id == "gemini-2.5-pro-exp-03-25"