import type {
  SerializedMessage,
  SubagentToken,
  SubagentTranscript,
} from "./types/messages";


export function appendStreamingToken(
  trace: SubagentTranscript,
  token: SubagentToken,
): SubagentTranscript {
  const previous = trace.streaming_drafts?.[token.stream_id];
  return {
    ...trace,
    streaming_drafts: {
      ...trace.streaming_drafts,
      [token.stream_id]: {
        source: token.source,
        text: `${previous?.text ?? ""}${token.text}`,
      },
    },
  };
}


export function appendCompletedTraceMessage(
  trace: SubagentTranscript,
  message: SerializedMessage,
  streamId?: string,
): SubagentTranscript {
  const streamingDrafts = { ...trace.streaming_drafts };
  if (streamId) delete streamingDrafts[streamId];
  return {
    ...trace,
    transcript: [...(trace.transcript ?? []), message],
    streaming_drafts: streamingDrafts,
  };
}
