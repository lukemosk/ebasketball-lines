import React, { useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine, Cell } from 'recharts';
import './App.css';

// Import your existing dashboard as a component
const MainDashboard = () => {
    const [selectedMiddleSize, setSelectedMiddleSize] = useState(2);
    const [selectedSide, setSelectedSide] = useState('either');
    const [selectedOdds, setSelectedOdds] = useState(-120);
    const [data, setData] = useState([]);
    const [stats, setStats] = useState({});
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    // Wilson confidence interval calculation
    const wilsonConfidenceInterval = (successes, trials, confidence = 0.95) => {
        if (trials === 0) return { lower: 0, upper: 0 };

        const z = 1.96; // 95% confidence
        const p = successes / trials;
        const denominator = 1 + (z * z) / trials;
        const centerAdjustment = p + (z * z) / (2 * trials);
        const marginError = z * Math.sqrt((p * (1 - p) + (z * z) / (4 * trials)) / trials);

        return {
            lower: Math.max(0, (centerAdjustment - marginError) / denominator),
            upper: Math.min(1, (centerAdjustment + marginError) / denominator)
        };
    };

    // Calculate breakeven rate based on odds
    const calculateBreakeven = (odds) => {
        const risk = Math.abs(odds);
        const win = 100;
        const loss = risk - win;
        return loss / (loss + 2 * win);
    };

    // Fetch data from backend
    React.useEffect(() => {
        fetchData();
    }, [selectedMiddleSize]);

    const fetchData = async () => {
        try {
            setLoading(true);

            const response = await fetch(`http://localhost:5000/api/middle-analysis?middle_size=${selectedMiddleSize}`);
            if (!response.ok) throw new Error('Failed to fetch data');
            const result = await response.json();

            if (result.success) {
                const enhancedData = result.data.map(point => {
                    const lowCI = wilsonConfidenceInterval(point.lowHits, point.totalGames);
                    const highCI = wilsonConfidenceInterval(point.highHits, point.totalGames);
                    const eitherCI = wilsonConfidenceInterval(point.eitherHits, point.totalGames);

                    return {
                        ...point,
                        lowCI,
                        highCI,
                        eitherCI
                    };
                });
                setData(enhancedData);
            } else {
                throw new Error(result.error || 'Unknown error');
            }

            const statsResponse = await fetch('http://localhost:5000/api/database-stats');
            if (statsResponse.ok) {
                const statsResult = await statsResponse.json();
                if (statsResult.success) {
                    setStats(statsResult.stats);
                }
            }

            setError(null);
        } catch (err) {
            setError(err.message);
            console.error('Error fetching data:', err);
        } finally {
            setLoading(false);
        }
    };

    const breakeven = calculateBreakeven(selectedOdds);

    const currentData = data.map(d => ({
        ...d,
        hitRate: selectedSide === 'low' ? d.lowHitRate :
            selectedSide === 'high' ? d.highHitRate : d.eitherHitRate,
        hits: selectedSide === 'low' ? d.lowHits :
            selectedSide === 'high' ? d.highHits : d.eitherHits,
        ci: selectedSide === 'low' ? d.lowCI :
            selectedSide === 'high' ? d.highCI : d.eitherCI
    }));

    const CustomTooltip = ({ active, payload, label }) => {
        if (active && payload && payload.length) {
            const data = payload[0].payload;
            const hitRate = payload[0].value;
            const isPositiveEV = hitRate > breakeven;

            return (
                <div style={{
                    backgroundColor: 'white',
                    padding: '12px',
                    border: '1px solid #ccc',
                    borderRadius: '4px',
                    boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
                }}>
                    <p style={{ fontWeight: 'bold', marginBottom: '4px' }}>{label}</p>
                    <p style={{ color: '#2563eb', marginBottom: '4px' }}>
                        Hit Rate: {(hitRate * 100).toFixed(1)}%
                    </p>
                    <p style={{ color: '#6b7280', marginBottom: '4px' }}>
                        Hits: {data.hits} / {data.totalGames} games
                    </p>
                    <p style={{ color: '#6b7280', marginBottom: '4px' }}>
                        95% CI: {(data.ci.lower * 100).toFixed(1)}% - {(data.ci.upper * 100).toFixed(1)}%
                    </p>
                    <p style={{
                        color: isPositiveEV ? '#10b981' : '#ef4444',
                        fontWeight: 'bold',
                        margin: 0
                    }}>
                        {isPositiveEV ? "POSITIVE EV" : "NEGATIVE EV"}
                    </p>
                </div>
            );
        }
        return null;
    };

    if (loading) {
        return (
            <div style={{ padding: '20px', textAlign: 'center' }}>
                <h2>Loading data...</h2>
                <p>Make sure the backend is running on http://localhost:5000</p>
            </div>
        );
    }

    if (error) {
        return (
            <div style={{ padding: '20px', color: 'red' }}>
                <h2>Error: {error}</h2>
                <p>Make sure the backend server is running:</p>
                <code>python middle_analysis_backend.py</code>
            </div>
        );
    }

    return (
        <div>
            <div style={{ marginBottom: '24px' }}>
                <h2 style={{ fontSize: '24px', fontWeight: 'bold', marginBottom: '16px' }}>
                    Hit Rate Analysis
                </h2>

                <div style={{
                    background: '#f3f4f6',
                    padding: '16px',
                    borderRadius: '8px',
                    marginBottom: '16px',
                    display: 'flex',
                    justifyContent: 'space-around'
                }}>
                    <div>
                        <strong>Total Games:</strong> {stats.total_games || 0}
                    </div>
                    <div>
                        <strong>Opener Spreads:</strong> {stats.opener_spreads || 0}
                    </div>
                    <div>
                        <strong>Quarter Lines:</strong> {stats.quarter_lines || 0}
                    </div>
                </div>

                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px', marginBottom: '16px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <label style={{ fontWeight: '500' }}>Middle Size:</label>
                        <select
                            value={selectedMiddleSize}
                            onChange={(e) => setSelectedMiddleSize(parseInt(e.target.value))}
                            style={{
                                border: '1px solid #d1d5db',
                                borderRadius: '4px',
                                padding: '4px 8px'
                            }}
                        >
                            {[1, 2, 3, 4, 5].map(size => (
                                <option key={size} value={size}>{size} points</option>
                            ))}
                        </select>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <label style={{ fontWeight: '500' }}>Side:</label>
                        <select
                            value={selectedSide}
                            onChange={(e) => setSelectedSide(e.target.value)}
                            style={{
                                border: '1px solid #d1d5db',
                                borderRadius: '4px',
                                padding: '4px 8px'
                            }}
                        >
                            <option value="low">Low (anchor high)</option>
                            <option value="high">High (anchor low)</option>
                            <option value="either">Either side</option>
                        </select>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <label style={{ fontWeight: '500' }}>Odds:</label>
                        <select
                            value={selectedOdds}
                            onChange={(e) => setSelectedOdds(parseInt(e.target.value))}
                            style={{
                                border: '1px solid #d1d5db',
                                borderRadius: '4px',
                                padding: '4px 8px'
                            }}
                        >
                            <option value={-130}>30 cents</option>
                            <option value={-140}>40 cents</option>
                            <option value={-150}>50 cents</option>
                            <option value={-160}>60 cents</option>
                        </select>
                    </div>
                </div>

                <div style={{ fontSize: '14px', color: '#6b7280', marginBottom: '16px' }}>
                    Breakeven rate at {selectedOdds}: <span style={{ fontWeight: '600', color: '#dc2626' }}>
                        {(breakeven * 100).toFixed(1)}%
                    </span>
                </div>
            </div>

            <ResponsiveContainer width="100%" height={400}>
                <BarChart
                    data={currentData}
                    margin={{ top: 20, right: 30, left: 20, bottom: 5 }}
                >
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="capture" />
                    <YAxis
                        tickFormatter={(value) => `${(value * 100).toFixed(0)}%`}
                        domain={[0, 'dataMax']}
                    />
                    <Tooltip content={<CustomTooltip />} />

                    <ReferenceLine
                        y={breakeven}
                        stroke="red"
                        strokeDasharray="5 5"
                        strokeWidth={2}
                        label={{ value: `Breakeven ${(breakeven * 100).toFixed(1)}%`, position: "right" }}
                    />

                    <Bar dataKey="hitRate" name="Hit Rate">
                        {currentData.map((entry, index) => (
                            <Cell
                                key={`cell-${index}`}
                                fill={entry.hitRate > breakeven ? "#10b981" : "#ef4444"}
                            />
                        ))}
                    </Bar>
                </BarChart>
            </ResponsiveContainer>

            <div style={{ marginTop: '16px' }}>
                <h3 style={{ fontSize: '18px', fontWeight: '600', marginBottom: '8px' }}>
                    Sample Size Details
                </h3>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px' }}>
                    {currentData.map((point, index) => {
                        const isSignificant = point.ci.lower > breakeven;
                        return (
                            <div key={index} style={{
                                backgroundColor: '#f9fafb',
                                padding: '12px',
                                borderRadius: '4px',
                                border: isSignificant ? '2px solid #10b981' : '1px solid #e5e7eb'
                            }}>
                                <div style={{ fontWeight: '500' }}>{point.capture}</div>
                                <div style={{ fontSize: '14px', color: '#6b7280' }}>
                                    n = {point.totalGames} games
                                </div>
                                <div style={{ fontSize: '14px', color: '#6b7280' }}>
                                    {point.hits} hits ({(point.hitRate * 100).toFixed(1)}%)
                                </div>
                                <div style={{ fontSize: '12px', color: '#6b7280', marginTop: '4px' }}>
                                    CI: {(point.ci.lower * 100).toFixed(1)}% - {(point.ci.upper * 100).toFixed(1)}%
                                </div>
                                {isSignificant && (
                                    <div style={{ fontSize: '12px', color: '#10b981', fontWeight: 'bold', marginTop: '4px' }}>
                                        ✓ Statistically significant
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
            </div>
        </div>
    );
};

// EV Heatmap component
const EVHeatmap = () => {
    const [selectedOdds, setSelectedOdds] = useState(-130);
    const [selectedSide, setSelectedSide] = useState('either');
    const [heatmapData, setHeatmapData] = useState([]);
    const [loading, setLoading] = useState(true);
    const [hoveredCell, setHoveredCell] = useState(null);

    // Calculate breakeven and EV
    const calculateBreakeven = (odds) => {
        const risk = Math.abs(odds);
        const win = 100;
        const loss = risk - win;
        return loss / (loss + 2 * win);
    };

    const calculateEV = (hitRate, odds) => {
        const risk = Math.abs(odds);
        const win = 100;
        const missNet = win - risk; // One wins, one loses
        const hitNet = 2 * win;     // Both win
        return (hitRate * hitNet) + ((1 - hitRate) * missNet);
    };

    // Fetch data for all middle sizes
    React.useEffect(() => {
        const fetchAllData = async () => {
            setLoading(true);
            const allData = [];

            try {
                // Fetch data for each middle size (1-5)
                for (let size = 1; size <= 5; size++) {
                    const response = await fetch(`http://localhost:5000/api/middle-analysis?middle_size=${size}`);
                    if (response.ok) {
                        const result = await response.json();
                        if (result.success) {
                            allData.push({ size, data: result.data });
                        }
                    }
                }

                // Transform data for heatmap
                const capturePoints = ['Opener', 'Q1 End', 'Q2 End', 'Q3 End'];
                const heatmapRows = capturePoints.map(capture => {
                    const row = { capture };

                    allData.forEach(({ size, data }) => {
                        const point = data.find(d => d.capture === capture);
                        if (point) {
                            const hitRate = selectedSide === 'low' ? point.lowHitRate :
                                selectedSide === 'high' ? point.highHitRate :
                                    point.eitherHitRate;
                            const hits = selectedSide === 'low' ? point.lowHits :
                                selectedSide === 'high' ? point.highHits :
                                    point.eitherHits;

                            row[`size${size}`] = {
                                hitRate,
                                hits,
                                totalGames: point.totalGames,
                                ev: calculateEV(hitRate, selectedOdds)
                            };
                        }
                    });

                    return row;
                });

                setHeatmapData(heatmapRows);
            } catch (error) {
                console.error('Error fetching heatmap data:', error);
            } finally {
                setLoading(false);
            }
        };

        fetchAllData();
    }, [selectedOdds, selectedSide]);

    const breakeven = calculateBreakeven(selectedOdds);

    // Color scale for EV
    const getColorForEV = (ev) => {
        if (ev > 20) return '#065f46'; // Dark green
        if (ev > 10) return '#10b981'; // Green
        if (ev > 5) return '#34d399';  // Light green
        if (ev > 0) return '#86efac';  // Very light green
        if (ev > -5) return '#fecaca'; // Light red
        if (ev > -10) return '#f87171'; // Red
        return '#dc2626'; // Dark red
    };

    const cellStyle = {
        padding: '16px',
        textAlign: 'center',
        border: '1px solid #e5e7eb',
        cursor: 'pointer',
        position: 'relative',
        transition: 'all 0.2s'
    };

    if (loading) {
        return (
            <div style={{ padding: '20px', textAlign: 'center' }}>
                <h2>Loading heatmap data...</h2>
            </div>
        );
    }

    return (
        <div style={{ padding: '20px' }}>
            <h2 style={{ fontSize: '24px', fontWeight: 'bold', marginBottom: '16px' }}>
                Expected Value Heatmap
            </h2>

            {/* Controls */}
            <div style={{ display: 'flex', gap: '16px', marginBottom: '20px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <label style={{ fontWeight: '500' }}>Side:</label>
                    <select
                        value={selectedSide}
                        onChange={(e) => setSelectedSide(e.target.value)}
                        style={{
                            border: '1px solid #d1d5db',
                            borderRadius: '4px',
                            padding: '4px 8px'
                        }}
                    >
                        <option value="low">Low (anchor high)</option>
                        <option value="high">High (anchor low)</option>
                        <option value="either">Either side</option>
                    </select>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <label style={{ fontWeight: '500' }}>Odds:</label>
                    <select
                        value={selectedOdds}
                        onChange={(e) => setSelectedOdds(parseInt(e.target.value))}
                        style={{
                            border: '1px solid #d1d5db',
                            borderRadius: '4px',
                            padding: '4px 8px'
                        }}
                    >
                        <option value={-130}>30 cents</option>
                        <option value={-140}>40 cents</option>
                        <option value={-150}>50 cents</option>
                        <option value={-160}>60 cents</option>
                    </select>
                </div>
            </div>

            <div style={{ marginBottom: '10px', fontSize: '14px', color: '#6b7280' }}>
                Breakeven at {Math.abs(selectedOdds) - 100} cents: {(breakeven * 100).toFixed(1)}%
            </div>

            {/* Heatmap Table */}
            <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: '20px' }}>
                <thead>
                    <tr>
                        <th style={{ ...cellStyle, fontWeight: 'bold', backgroundColor: '#f9fafb' }}>
                            Capture Point
                        </th>
                        {[1, 2, 3, 4, 5].map(size => (
                            <th key={size} style={{ ...cellStyle, fontWeight: 'bold', backgroundColor: '#f9fafb' }}>
                                {size}pt Middle
                            </th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {heatmapData.map((row, idx) => (
                        <tr key={idx}>
                            <td style={{ ...cellStyle, fontWeight: '500', backgroundColor: '#f9fafb' }}>
                                {row.capture}
                            </td>
                            {[1, 2, 3, 4, 5].map(size => {
                                const cell = row[`size${size}`];
                                if (!cell) {
                                    return <td key={size} style={cellStyle}>-</td>;
                                }

                                const isHovered = hoveredCell === `${idx}-${size}`;
                                const cellColor = getColorForEV(cell.ev);

                                return (
                                    <td
                                        key={size}
                                        style={{
                                            ...cellStyle,
                                            backgroundColor: cellColor,
                                            color: cell.ev > 0 ? 'white' : 'white',
                                            fontWeight: cell.ev > 0 ? 'bold' : 'normal',
                                            transform: isHovered ? 'scale(1.05)' : 'scale(1)',
                                            boxShadow: isHovered ? '0 4px 6px rgba(0,0,0,0.1)' : 'none'
                                        }}
                                        onMouseEnter={() => setHoveredCell(`${idx}-${size}`)}
                                        onMouseLeave={() => setHoveredCell(null)}
                                    >
                                        <div style={{ fontSize: '18px' }}>
                                            ${cell.ev.toFixed(1)}
                                        </div>
                                        <div style={{ fontSize: '12px', opacity: 0.9 }}>
                                            {(cell.hitRate * 100).toFixed(1)}%
                                        </div>
                                        <div style={{ fontSize: '10px', opacity: 0.7 }}>
                                            n={cell.totalGames}
                                        </div>
                                    </td>
                                );
                            })}
                        </tr>
                    ))}
                </tbody>
            </table>

            {/* Hover tooltip */}
            {hoveredCell && (() => {
                const [rowIdx, size] = hoveredCell.split('-').map(Number);
                const row = heatmapData[rowIdx];
                const cell = row[`size${size}`];

                return (
                    <div style={{
                        position: 'fixed',
                        bottom: '20px',
                        left: '50%',
                        transform: 'translateX(-50%)',
                        backgroundColor: 'rgba(0, 0, 0, 0.9)',
                        color: 'white',
                        padding: '16px',
                        borderRadius: '8px',
                        boxShadow: '0 4px 6px rgba(0,0,0,0.1)',
                        zIndex: 1000
                    }}>
                        <div style={{ fontWeight: 'bold', marginBottom: '8px' }}>
                            {row.capture} - {size}pt Middle
                        </div>
                        <div>Hit Rate: {(cell.hitRate * 100).toFixed(1)}%</div>
                        <div>Expected Value: ${cell.ev.toFixed(2)} per $250 bet</div>
                        <div>Sample Size: {cell.totalGames} games ({cell.hits} hits)</div>
                        <div style={{ marginTop: '8px', fontSize: '12px', opacity: 0.8 }}>
                            ROI: {((cell.ev / 250) * 100).toFixed(1)}%
                        </div>
                    </div>
                );
            })()}

            {/* Legend */}
            <div style={{ marginTop: '20px' }}>
                <h3 style={{ fontSize: '16px', fontWeight: '600', marginBottom: '8px' }}>
                    Color Legend (EV per $250 bet)
                </h3>
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    {[
                        { color: '#065f46', label: '> $20' },
                        { color: '#10b981', label: '$10 to $20' },
                        { color: '#34d399', label: '$5 to $10' },
                        { color: '#86efac', label: '$0 to $5' },
                        { color: '#fecaca', label: '-$5 to $0' },
                        { color: '#f87171', label: '-$10 to -$5' },
                        { color: '#dc2626', label: '< -$10' }
                    ].map(({ color, label }) => (
                        <div key={color} style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                            <div style={{
                                width: '20px',
                                height: '20px',
                                backgroundColor: color,
                                border: '1px solid #d1d5db'
                            }} />
                            <span style={{ fontSize: '12px' }}>{label}</span>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
};

// Distribution Analysis component
const DistributionAnalysis = () => {
    const [selectedCapture, setSelectedCapture] = useState('opener');
    const [selectedMiddleSize, setSelectedMiddleSize] = useState(3);
    const [distributionData, setDistributionData] = useState([]);
    const [loading, setLoading] = useState(true);
    const [stats, setStats] = useState({});

    React.useEffect(() => {
        fetchDistributionData();
    }, [selectedCapture]);

    const fetchDistributionData = async () => {
        try {
            setLoading(true);

            // For now, we'll simulate the distribution data
            // In a real implementation, you'd add an API endpoint that returns the raw game data
            const response = await fetch('http://localhost:5000/api/database-stats');
            if (response.ok) {
                const result = await response.json();
                if (result.success) {
                    setStats(result.stats);
                }
            }

            // Simulate distribution data for the selected capture point
            // This would normally come from your backend
            const generateDistribution = () => {
                const data = [];
                for (let d = -10; d <= 10; d += 0.5) {
                    // Simulate a roughly normal distribution centered slightly above 0
                    const base = Math.exp(-Math.pow(d - 0.5, 2) / 8);
                    const count = Math.round(base * 15 + Math.random() * 3);
                    data.push({
                        delta: d,
                        count: count,
                        isInLowWindow: d > -selectedMiddleSize && d < 0,
                        isInHighWindow: d > 0 && d < selectedMiddleSize
                    });
                }
                return data;
            };

            setDistributionData(generateDistribution());
            setLoading(false);
        } catch (error) {
            console.error('Error fetching distribution data:', error);
            setLoading(false);
        }
    };

    const maxCount = Math.max(...distributionData.map(d => d.count));

    if (loading) {
        return (
            <div style={{ padding: '20px', textAlign: 'center' }}>
                <h2>Loading distribution data...</h2>
            </div>
        );
    }

    return (
        <div style={{ padding: '20px' }}>
            <h2 style={{ fontSize: '24px', fontWeight: 'bold', marginBottom: '16px' }}>
                Distribution Analysis: D = Result - Line
            </h2>

            <p style={{ marginBottom: '20px', color: '#6b7280' }}>
                Shows where game results fall relative to the captured line.
                Shaded areas represent your middle windows where both bets would win.
            </p>

            {/* Controls */}
            <div style={{ display: 'flex', gap: '16px', marginBottom: '20px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <label style={{ fontWeight: '500' }}>Capture Point:</label>
                    <select
                        value={selectedCapture}
                        onChange={(e) => setSelectedCapture(e.target.value)}
                        style={{
                            border: '1px solid #d1d5db',
                            borderRadius: '4px',
                            padding: '4px 8px'
                        }}
                    >
                        <option value="opener">Opener</option>
                        <option value="q1">Q1 End</option>
                        <option value="q2">Q2 End</option>
                        <option value="q3">Q3 End</option>
                    </select>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <label style={{ fontWeight: '500' }}>Middle Size:</label>
                    <select
                        value={selectedMiddleSize}
                        onChange={(e) => setSelectedMiddleSize(parseInt(e.target.value))}
                        style={{
                            border: '1px solid #d1d5db',
                            borderRadius: '4px',
                            padding: '4px 8px'
                        }}
                    >
                        {[1, 2, 3, 4, 5].map(size => (
                            <option key={size} value={size}>{size} points</option>
                        ))}
                    </select>
                </div>
            </div>

            {/* Histogram */}
            <div style={{
                position: 'relative',
                backgroundColor: '#f9fafb',
                padding: '40px 20px 20px',
                borderRadius: '8px',
                marginBottom: '20px'
            }}>
                {/* Y-axis label */}
                <div style={{
                    position: 'absolute',
                    left: '10px',
                    top: '20px',
                    fontSize: '12px',
                    color: '#6b7280'
                }}>
                    Count
                </div>

                {/* Histogram bars */}
                <div style={{
                    display: 'flex',
                    alignItems: 'flex-end',
                    height: '300px',
                    borderBottom: '2px solid #374151',
                    borderLeft: '2px solid #374151',
                    paddingLeft: '20px'
                }}>
                    {distributionData.map((bar, idx) => {
                        const height = (bar.count / maxCount) * 280;
                        let color = '#9ca3af'; // Default gray

                        if (bar.isInLowWindow) color = '#3b82f6'; // Blue for low window
                        if (bar.isInHighWindow) color = '#10b981'; // Green for high window
                        if (bar.delta === 0) color = '#ef4444'; // Red for push (0)

                        return (
                            <div
                                key={idx}
                                style={{
                                    width: '20px',
                                    height: `${height}px`,
                                    backgroundColor: color,
                                    marginRight: '2px',
                                    position: 'relative',
                                    cursor: 'pointer',
                                    transition: 'all 0.2s'
                                }}
                                title={`D=${bar.delta}: ${bar.count} games`}
                            >
                                {/* Show count on hover */}
                                {bar.count > 0 && (
                                    <div style={{
                                        position: 'absolute',
                                        top: '-20px',
                                        left: '50%',
                                        transform: 'translateX(-50%)',
                                        fontSize: '10px',
                                        opacity: 0,
                                        transition: 'opacity 0.2s'
                                    }}
                                        className="count-label">
                                        {bar.count}
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>

                {/* X-axis labels */}
                <div style={{
                    display: 'flex',
                    paddingLeft: '20px',
                    marginTop: '10px'
                }}>
                    {distributionData.filter((_, idx) => idx % 4 === 0).map((bar, idx) => (
                        <div key={idx} style={{
                            width: '80px',
                            textAlign: 'center',
                            fontSize: '12px',
                            color: '#6b7280'
                        }}>
                            {bar.delta}
                        </div>
                    ))}
                </div>

                {/* X-axis label */}
                <div style={{
                    textAlign: 'center',
                    marginTop: '10px',
                    fontSize: '14px',
                    color: '#374151'
                }}>
                    D = Result - Line (points)
                </div>
            </div>

            {/* Legend and explanation */}
            <div style={{
                backgroundColor: '#f3f4f6',
                padding: '16px',
                borderRadius: '8px'
            }}>
                <h3 style={{ fontSize: '16px', fontWeight: '600', marginBottom: '12px' }}>
                    Understanding the Distribution
                </h3>

                <div style={{ display: 'flex', gap: '20px', marginBottom: '12px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <div style={{ width: '20px', height: '20px', backgroundColor: '#3b82f6' }} />
                        <span>Low window hits (-{selectedMiddleSize} to 0)</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <div style={{ width: '20px', height: '20px', backgroundColor: '#10b981' }} />
                        <span>High window hits (0 to +{selectedMiddleSize})</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <div style={{ width: '20px', height: '20px', backgroundColor: '#ef4444' }} />
                        <span>Push (D = 0)</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <div style={{ width: '20px', height: '20px', backgroundColor: '#9ca3af' }} />
                        <span>No hit</span>
                    </div>
                </div>

                <div style={{ fontSize: '14px', color: '#6b7280', lineHeight: '1.6' }}>
                    <p style={{ marginBottom: '8px' }}>
                        <strong>How to read:</strong> This histogram shows how actual game results
                        differ from the line at the selected capture point.
                    </p>
                    <p style={{ marginBottom: '8px' }}>
                        • <strong>D {'>'} 0:</strong> Final margin exceeded the line (favorite covered)
                    </p>
                    <p style={{ marginBottom: '8px' }}>
                        • <strong>D {'<'} 0:</strong> Final margin fell short of the line (underdog covered)
                    </p>
                    <p>
                        • <strong>Colored regions:</strong> Your middle windows where both bets would win
                    </p>
                </div>
            </div>

            {/* Summary stats */}
            <div style={{
                marginTop: '20px',
                display: 'grid',
                gridTemplateColumns: 'repeat(2, 1fr)',
                gap: '16px'
            }}>
                <div style={{
                    backgroundColor: '#dbeafe',
                    padding: '16px',
                    borderRadius: '8px',
                    textAlign: 'center'
                }}>
                    <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#3b82f6' }}>
                        {distributionData.filter(d => d.isInLowWindow).reduce((sum, d) => sum + d.count, 0)}
                    </div>
                    <div style={{ fontSize: '14px', color: '#6b7280' }}>
                        Low Window Hits
                    </div>
                    <div style={{ fontSize: '12px', color: '#6b7280', marginTop: '4px' }}>
                        (line - {selectedMiddleSize} to line)
                    </div>
                </div>

                <div style={{
                    backgroundColor: '#d1fae5',
                    padding: '16px',
                    borderRadius: '8px',
                    textAlign: 'center'
                }}>
                    <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#10b981' }}>
                        {distributionData.filter(d => d.isInHighWindow).reduce((sum, d) => sum + d.count, 0)}
                    </div>
                    <div style={{ fontSize: '14px', color: '#6b7280' }}>
                        High Window Hits
                    </div>
                    <div style={{ fontSize: '12px', color: '#6b7280', marginTop: '4px' }}>
                        (line to line + {selectedMiddleSize})
                    </div>
                </div>
            </div>

            <style>{`
        .count-label:hover {
          opacity: 1 !important;
        }
      `}</style>
        </div>
    );
};

// Main App with navigation
function App() {
    const [currentPage, setCurrentPage] = useState('dashboard');

    const navStyle = {
        display: 'flex',
        gap: '20px',
        padding: '20px',
        borderBottom: '2px solid #e5e7eb',
        marginBottom: '20px',
        backgroundColor: '#f9fafb'
    };

    const navButtonStyle = (isActive) => ({
        padding: '8px 16px',
        border: 'none',
        borderRadius: '4px',
        cursor: 'pointer',
        backgroundColor: isActive ? '#3b82f6' : 'white',
        color: isActive ? 'white' : '#374151',
        fontWeight: isActive ? 'bold' : 'normal',
        transition: 'all 0.2s'
    });

    return (
        <div style={{ minHeight: '100vh', backgroundColor: 'white' }}>
            {/* Navigation */}
            <nav style={navStyle}>
                <button
                    style={navButtonStyle(currentPage === 'dashboard')}
                    onClick={() => setCurrentPage('dashboard')}
                >
                    Hit Rate Dashboard
                </button>
                <button
                    style={navButtonStyle(currentPage === 'heatmap')}
                    onClick={() => setCurrentPage('heatmap')}
                >
                    EV Heatmap
                </button>
                <button
                    style={navButtonStyle(currentPage === 'distribution')}
                    onClick={() => setCurrentPage('distribution')}
                >
                    Distribution Analysis
                </button>
            </nav>

            {/* Page Content */}
            <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '24px' }}>
                {currentPage === 'dashboard' && <MainDashboard />}
                {currentPage === 'heatmap' && <EVHeatmap />}
                {currentPage === 'distribution' && <DistributionAnalysis />}
            </div>
        </div>
    );
}

export default App;