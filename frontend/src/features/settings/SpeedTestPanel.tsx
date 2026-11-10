import { useState } from 'react';
import { Button } from '../../components/ui/Button';
import { ConfirmDialog } from '../../components/ui/ConfirmDialog';
import { Notice } from '../../components/ui/Notice';
import { Select } from '../../components/ui/Select';
import { Slider } from '../../components/ui/Slider';
import { StatusLight, type StatusTone } from '../../components/ui/StatusLight';
import { modelSelectOptions, type ModelLike } from '../../lib/model-options';
import { SettingRow } from './forms';
import { SpeedChart } from './SpeedChart';
import { useSpeedTest, type SpeedTestPhase } from './useSpeedTest';

const MIN_CONTEXT = 1_000;
const MAX_CONTEXT = 1_000_000;
const DEFAULT_CONTEXT = 128_000;

const PHASE: Record<Exclude<SpeedTestPhase, 'idle'>, { word: string; tone: StatusTone }> = {
  running: { word: 'Testing', tone: 'neutral' },
  done: { word: 'Done', tone: 'ok' },
  stopped: { word: 'Stopped', tone: 'warn' },
  failed: { word: 'Did not finish', tone: 'bad' },
};

const whole = (n: number) => Math.round(n).toLocaleString('en-GB');

/**
 * The speed test: fills a model's memory step by step and times each step. A graph fills in as it
 * runs, with four figures under it and a way to stop.
 */
export function SpeedTestPanel({ models }: { models: ModelLike[] }) {
  const [target, setTarget] = useState('');
  const [context, setContext] = useState(DEFAULT_CONTEXT);
  const [confirming, setConfirming] = useState(false);
  const [tested, setTested] = useState('');
  const { phase, state, error, run, stop } = useSpeedTest();
  const running = phase === 'running';

  return (
    <>
      <SettingRow label="Model to test" hint="Loads this model alone and times its answers." wide>
        {({ id }) => (
          <div className="speed-pick">
            <Select
              id={id}
              aria-label="Model to test"
              placeholder="Choose a model"
              searchable
              searchPlaceholder="Search models"
              value={target}
              options={modelSelectOptions(models)}
              onChange={setTarget}
            />
            <Button
              variant="secondary"
              disabled={!target}
              loading={running}
              reason="Choose a model first"
              onClick={() => setConfirming(true)}
            >
              Run
            </Button>
          </div>
        )}
      </SettingRow>
      <SettingRow
        label="Fill its memory to"
        hint="In tokens. The test stops when it gets there."
        wide
      >
        {() => (
          <Slider
            label="Fill its memory to"
            value={context}
            onChange={setContext}
            min={MIN_CONTEXT}
            max={MAX_CONTEXT}
            step={1000}
            decimals={0}
          />
        )}
      </SettingRow>

      {phase !== 'idle' ? (
        <div className="speed-panel">
          <div className="speed-panel__head">
            <StatusLight
              label={`${PHASE[phase].word} · ${tested}`}
              tone={PHASE[phase].tone}
              busy={running}
            />
            {running ? (
              <Button variant="secondary" onClick={stop}>
                Stop
              </Button>
            ) : null}
          </div>
          {state.status ? <p className="ui-hint speed-panel__status">{state.status}</p> : null}
          <SpeedChart points={state.points} />
          <dl className="facts">
            <div>
              <dt className="sec">Progress</dt>
              <dd>
                {whole(state.contextTokens)} of {whole(context)} tokens
              </dd>
            </div>
            <div>
              <dt className="sec">First word after</dt>
              <dd>{`${(state.avgTtftMs / 1000).toFixed(1)} s`}</dd>
            </div>
            <div>
              <dt className="sec">Reading speed</dt>
              <dd>{`${whole(state.avgPrefillTps)} tokens a second`}</dd>
            </div>
            <div>
              <dt className="sec">Writing speed</dt>
              <dd>{`${state.avgDecodeTps.toFixed(1)} tokens a second`}</dd>
            </div>
          </dl>
          {state.warnings.length > 0 && phase !== 'failed' ? (
            <ul className="ui-hint speed-panel__warnings">
              {state.warnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
      {error ? <Notice tone="bad">{error}</Notice> : null}
      <ConfirmDialog
        open={confirming}
        title="Run the speed test?"
        message="Every loaded model is unloaded first, then this one is loaded and tested until its memory is filled to the amount chosen."
        confirmLabel="Run the test"
        onCancel={() => setConfirming(false)}
        onConfirm={() => {
          setConfirming(false);
          setTested(target);
          run(target, context);
        }}
      />
    </>
  );
}
