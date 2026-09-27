/**
 * Server-Sent Events subscriber with automatic reconnection and Last-Event-ID tracking.
 */

import { StudioEvent } from "./types";

export function subscribeToRunEvents(
  runId: string,
  handlers: {
    onEvent?: (event: StudioEvent) => void;
    onEvents?: (events: StudioEvent[]) => void;
    onOpen?: () => void;
    onError?: (err: Event) => void;
  },
  sinceSeq?: number
): () => void {
  let url = `/api/runs/${encodeURIComponent(runId)}/events`;
  if (sinceSeq !== undefined) {
    url += `?since=${sinceSeq}`;
  }

  const es = new EventSource(url);
  let buffer: StudioEvent[] = [];
  let frameId: number | ReturnType<typeof setTimeout> | null = null;

  const flush = () => {
    if (buffer.length > 0) {
      const batch = buffer;
      buffer = [];
      if (handlers.onEvents) {
        handlers.onEvents(batch);
      } else if (handlers.onEvent) {
        for (const ev of batch) {
          handlers.onEvent(ev);
        }
      }
    }
    frameId = null;
  };

  const scheduleFlush = () => {
    if (frameId === null) {
      if (typeof requestAnimationFrame !== "undefined") {
        frameId = requestAnimationFrame(flush);
      } else {
        frameId = setTimeout(flush, 16);
      }
    }
  };

  es.onopen = () => {
    handlers.onOpen?.();
  };

  es.onmessage = (messageEvent) => {
    try {
      const data = JSON.parse(messageEvent.data) as StudioEvent;
      buffer.push(data);
      scheduleFlush();
    } catch (err) {
      console.error("Failed to parse StudioEvent from SSE:", err);
    }
  };

  es.onerror = (err) => {
    handlers.onError?.(err);
  };

  return () => {
    if (frameId !== null) {
      if (typeof cancelAnimationFrame !== "undefined" && typeof frameId === "number") {
        cancelAnimationFrame(frameId);
      } else {
        clearTimeout(frameId as any);
      }
      frameId = null;
    }
    flush();
    es.close();
  };
}

export function subscribeToEvaluationJobEvents(
  jobId: string,
  handlers: {
    onEvent?: (event: StudioEvent) => void;
    onEvents?: (events: StudioEvent[]) => void;
    onOpen?: () => void;
    onError?: (err: Event) => void;
  },
  sinceSeq?: number
): () => void {
  let url = `/api/evaluation/jobs/${encodeURIComponent(jobId)}/stream`;
  if (sinceSeq !== undefined) {
    url += `?since=${sinceSeq}`;
  }

  const es = new EventSource(url);
  let buffer: StudioEvent[] = [];
  let frameId: number | ReturnType<typeof setTimeout> | null = null;

  const flush = () => {
    if (buffer.length > 0) {
      const batch = buffer;
      buffer = [];
      if (handlers.onEvents) {
        handlers.onEvents(batch);
      } else if (handlers.onEvent) {
        for (const ev of batch) {
          handlers.onEvent(ev);
        }
      }
    }
    frameId = null;
  };

  const scheduleFlush = () => {
    if (frameId === null) {
      if (typeof requestAnimationFrame !== "undefined") {
        frameId = requestAnimationFrame(flush);
      } else {
        frameId = setTimeout(flush, 16);
      }
    }
  };

  es.onopen = () => {
    handlers.onOpen?.();
  };

  es.onmessage = (messageEvent) => {
    try {
      const data = JSON.parse(messageEvent.data) as StudioEvent;
      buffer.push(data);
      scheduleFlush();
    } catch (err) {
      console.error("Failed to parse StudioEvent from evaluation SSE:", err);
    }
  };

  es.onerror = (err) => {
    handlers.onError?.(err);
  };

  return () => {
    if (frameId !== null) {
      if (typeof cancelAnimationFrame !== "undefined" && typeof frameId === "number") {
        cancelAnimationFrame(frameId);
      } else {
        clearTimeout(frameId as any);
      }
      frameId = null;
    }
    flush();
    es.close();
  };
}
