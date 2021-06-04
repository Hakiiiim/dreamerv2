import numpy as np


class Driver:

    def __init__(self, envs, **kwargs):
        self._envs = envs
        self._kwargs = kwargs
        self._on_episodes = []
        self._on_steps = []
        self.reset()

    def on_step(self, callback):
        self._on_steps.append(callback)

    def on_episode(self, callback):
        self._on_episodes.append(callback)

    def reset(self):
        self._obs = [None] * len(self._envs)
        self._dones = [True] * len(self._envs)
        self._eps = [None] * len(self._envs)
        self._state = None

    def __call__(self, policy, steps=0, episodes=0):
        step, episode = 0, 0
        while step < steps or episode < episodes:
            for i, done in enumerate(self._dones):
                # initially dones are all True so the envs are reset
                if done:
                    self._obs[i] = self._envs[i].reset()

                    # self._eps = List[episode = List[Dict(Transition = obs, rew, dis)]]
                    self._eps[i] = [{**self._obs[i], 'reward': 0.0, 'discount': 1.0}]

            # reformat obs
            obs = {k: np.stack([o[k] for o in self._obs]) for k in self._obs[0]}

            # select action using actor
            actions, self._state = policy(obs, self._state, **self._kwargs)

            # reformat
            actions = [
                {k: np.array(actions[k][i]) for k in actions}
                for i in range(len(self._envs))]

            # one action per env
            assert len(actions) == len(self._envs)

            # play the actions in the corresponding envs
            results = [e.step(a) for e, a in zip(self._envs, actions)]

            # i is for environment number i
            for i, (act, (ob, rew, done, info)) in enumerate(zip(actions, results)):
                # format
                obs = {k: self._convert(v) for k, v in obs.items()}

                disc = info.get('discount', np.array(1 - float(done)))

                # write structured transition
                tran = {**ob, **act, 'reward': rew, 'discount': disc}

                # append episode
                self._eps[i].append(tran)

                # increment step, train or log if applicable (only on train_driver)
                [callback(tran, **self._kwargs) for callback in self._on_steps]

                if done:
                    ep = self._eps[i]
                    for key, value in ep[1].items():
                        if key not in ep[0]:
                            ep[0][key] = 0 * value
                    ep = {k: self._convert([t[k] for t in ep]) for k in ep[0]}

                    # calls per_episode and adds ep to replay_buffer
                    [callback(ep, **self._kwargs) for callback in self._on_episodes]

            obs, _, dones = zip(*[p[:3] for p in results])

            # store
            self._obs = list(obs)
            self._dones = list(dones)

            # count all episodes that were terminated
            episode += sum(dones)

            step += len(dones)

    def _convert(self, value):
        value = np.array(value)
        if np.issubdtype(value.dtype, np.floating):
            return value.astype(np.float32)
        elif np.issubdtype(value.dtype, np.signedinteger):
            return value.astype(np.int32)
        elif np.issubdtype(value.dtype, np.uint8):
            return value.astype(np.uint8)
        return value
