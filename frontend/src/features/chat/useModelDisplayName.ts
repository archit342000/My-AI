import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { modelConfigQuery } from '../../api/settings';
import { displayModelName, modelDisplayNames } from '../../lib/model-options';

/** Returns a function that turns a model id into the name the legacy UI shows (the id until the config is loaded). */
export function useModelDisplayName(): (id: string) => string {
  const config = useQuery(modelConfigQuery);
  const names = useMemo(() => modelDisplayNames(config.data ?? {}), [config.data]);
  return (id) => displayModelName(id, names);
}
