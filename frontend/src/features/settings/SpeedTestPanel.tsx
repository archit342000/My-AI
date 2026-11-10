import { useState } from 'react';
import { ConfirmDialog } from '../../components/ui/ConfirmDialog';
import { Button } from '../../components/ui/Button';
import { Field } from '../../components/ui/Field';
import { Select } from '../../components/ui/Select';
import { Slider } from '../../components/ui/Slider';
import { modelSelectOptions, type ModelLike } from '../../lib/model-options';
import { Section, Status } from './forms';
import { SpeedChart } from './SpeedChart';
import { useSpeedTest } from './useSpeedTest';

const MIN_CONTEXT = 1_000;
const MAX_CONTEXT = 1_000_000;
const DEFAULT_CONTEXT = 128_000;

/** Speed test of the model manager: choose a model and target context, run, watch the figures and the chart. */
export function SpeedTestPanel({ models }: { models: ModelLike[] }) {
  const [target, setTarget] = useState('');
  const [context, setContext] = useState(DEFAULT_CONTEXT);
  const [confirming, setConfirming] = useState(false);
  const { phase, state, error, run, stop } = useSpeedTest();
  const running = phase === 'running';

  return (
    <Section title="Speed test">
      <Field label="Speed test target">
        {(c) => (
          <Select
            id={c.id}
            placeholder="Select a model"
            searchable
            searchPlaceholder="Search models"
            value={target}
            options={modelSelectOptions(models)}
            onChange={setTarget}
          />
        )}
      </Field>
      <div className="speed-test__context">
        <span className="speed-test__context-label">Target context (tokens)</span>
        <Slider
          label="Target context (tokens)"
          value={context}
          onChange={setContext}
          min={MIN_CONTEXT}
          max={MAX_CONTEXT}
          step={1000}
          decimals={0}
        />
      </div>
      <div className="speed-test__actions">
        <Button variant="primary" disabled={!target || running} onClick={() => setConfirming(true)}>
          {running ? 'Running…' : 'Run speed test'}
        </Button>
        {running ? (
          <Button variant="secondary" onClick={stop}>
            Stop
          </Button>
        ) : null}
      </div>
      {phase !== 'idle' ? (
        <>
          <div className="speed-test__status" role="status">
            {state.status || 'Starting…'}
          </div>
          <dl className="speed-test__figures">
            <div>
              <dt>Tokens in context</dt>
              <dd>{state.contextTokens.toLocaleString('en-US')}</dd>
            </div>
            <div>
              <dt>Avg time to first token</dt>
              <dd>{`${Math.round(state.avgTtftMs)} ms`}</dd>
            </div>
            <div>
              <dt>Avg prefill speed</dt>
              <dd>{`${state.avgPrefillTps.toFixed(2)} tok/s`}</dd>
            </div>
            <div>
              <dt>Avg decode speed</dt>
              <dd>{`${state.avgDecodeTps.toFixed(2)} tok/s`}</dd>
            </div>
          </dl>
          <SpeedChart points={state.points} />
          {state.warnings.length > 0 && phase !== 'failed' ? (
            <ul className="speed-test__warnings">
              {state.warnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          ) : null}
        </>
      ) : null}
      <Status message={error} tone="error" />
      <ConfirmDialog
        open={confirming}
        title="Run the speed test?"
        message="The test unloads every loaded model, loads the selected one and runs until the target context is reached."
        confirmLabel="Run"
        onCancel={() => setConfirming(false)}
        onConfirm={() => {
          setConfirming(false);
          run(target, context);
        }}
      />
    </Section>
  );
}
