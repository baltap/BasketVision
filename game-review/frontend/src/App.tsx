import { Navigate, Route, Routes } from 'react-router-dom';
import { Shell } from './components/Shell';
import { GamesPage } from './pages/Games';
import { TeamPage } from './pages/Team';
import { ReviewPage } from './pages/Review';
import { TimelinePage } from './pages/Timeline';
import { PlayerPage } from './pages/Player';
import { RosterPage } from './pages/Roster';
import { StoragePage } from './pages/Storage';
import { NewGamePage } from './pages/NewGame';
import { JobPage } from './pages/Job';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<GamesPage />} />
      <Route path="/new" element={<NewGamePage />} />
      <Route path="/jobs/:jid" element={<JobPage />} />
      <Route path="/g/:gid" element={<Shell />}>
        <Route index element={<Navigate to="team" replace />} />
        <Route path="team" element={<TeamPage />} />
        <Route path="review" element={<ReviewPage />} />
        <Route path="timeline" element={<TimelinePage />} />
        <Route path="players/:slug" element={<PlayerPage />} />
        <Route path="roster" element={<RosterPage />} />
        <Route path="storage" element={<StoragePage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
