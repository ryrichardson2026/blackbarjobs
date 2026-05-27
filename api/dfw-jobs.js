let cache = { data: null, ts: 0 };
const TTL = 2 * 60 * 60 * 1000; // 2 hours

module.exports = async (req, res) => {
  try {
    if (cache.data && Date.now() - cache.ts < TTL) {
      return res.status(200).json(cache.data);
    }

    const response = await fetch(
      'https://api.jobdatalake.com/v1/jobs?q=security&location=Dallas&per_page=50&sort_by=posted_at:desc',
      {
        headers: {
          'X-API-Key': process.env.JOBDATALAKE_API_KEY
        }
      }
    );

    const data = await response.json();

    const filteredJobs = data.jobs.filter(job => {
      const title = job.title.toLowerCase();
      return !title.includes('cloud')
        && !title.includes('cyber')
        && !title.includes('architect')
        && !title.includes('engineer')
        && !title.includes('information security');
    });

    const result = { jobs: filteredJobs };
    cache = { data: result, ts: Date.now() };

    res.status(200).json(result);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
};
