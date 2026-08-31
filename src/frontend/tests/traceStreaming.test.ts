import assert from "node:assert/strict";
import test from "node:test";

import {
  appendStreamingToken,
  appendCompletedTraceMessage,
} from "../src/traceStreaming.ts";


const baseTrace = () => ({
  tool_id: "inv-1",
  agent_name: "Coding Agent",
  avatar: "code",
  transcript: [],
  raw_state: null,
  invocation_id: "inv-1",
});


test("token drafts append independently by stream", () => {
  let trace = appendStreamingToken(baseTrace(), {
    stream_id: "root/message-1",
    source: "Coding Agent",
    text: "Hel",
  });
  trace = appendStreamingToken(trace, {
    stream_id: "nested/message-2",
    source: "researcher",
    text: "Sub",
  });
  trace = appendStreamingToken(trace, {
    stream_id: "root/message-1",
    source: "Coding Agent",
    text: "lo",
  });

  assert.deepEqual(trace.streaming_drafts, {
    "root/message-1": { source: "Coding Agent", text: "Hello" },
    "nested/message-2": { source: "researcher", text: "Sub" },
  });
});


test("completed messages clear only their matching draft", () => {
  let trace = appendStreamingToken(baseTrace(), {
    stream_id: "root/message-1",
    source: "Coding Agent",
    text: "Hello",
  });
  trace = appendStreamingToken(trace, {
    stream_id: "nested/message-2",
    source: "researcher",
    text: "Still running",
  });
  const message = {
    id: "message-1",
    type: "ai",
    name: null,
    content: "Hello",
    avatar: "code",
  };

  trace = appendCompletedTraceMessage(trace, message, "root/message-1");

  assert.deepEqual(trace.transcript, [message]);
  assert.deepEqual(trace.streaming_drafts, {
    "nested/message-2": { source: "researcher", text: "Still running" },
  });
});
