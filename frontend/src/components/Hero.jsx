import React from 'react'
import { Box, Typography, Button } from '@mui/material'
import { motion } from 'framer-motion'

export default function Hero({ onCta }) {
  return (
    <Box
      sx={{
        py: 8,
        minHeight: { xs: '100vh', md: '100vh' },
        display: 'flex',
        alignItems: 'center',
        background: 'linear-gradient(180deg, rgba(7,17,38,1) 0%, rgba(15,23,36,1) 100%)',
        color: '#e6eef8',
        '@supports (height: 100dvh)': {
          minHeight: { xs: '100dvh', md: '100dvh' },
        },
      }}
    >
      <Box sx={{ maxWidth: 1200, mx: 'auto', display: 'flex', alignItems: 'center', gap: 4, px: 3, flexWrap: 'wrap' }}>

        {/* Left Text Content */}
        <Box sx={{ flex: 1, minWidth: 300 }}>
          <Typography variant="h3" sx={{ fontWeight: 700, mb: 2 }}>
            Spot the Fake — AI-Powered Phishing & Website Fraud Detection
          </Typography>
          <Typography variant="h6" sx={{ color: 'rgba(230,238,248,0.8)', fontWeight: 400,mb: 4 }}>
            Protect your users and brand with advanced ML + LLM-powered threat detection. Fast, explainable, and easy to integrate.
          </Typography>
          <Box sx={{ display: 'flex', gap: 2 }}>
            <Button variant="contained" color="primary" onClick={onCta}>
              Try Demo
            </Button>
            <Button variant="outlined" color="inherit" onClick={() => window.open('https://github.com/rishiigupta04/spot-the-fake', '_blank')}>
              View on GitHub
            </Button>
          </Box>
        </Box>

        {/* Right Decorative Side */}
        <Box sx={{ flex: 1, minWidth: 300, display: { xs: 'none', md: 'block' }, position: 'relative', height: 400 }}>

          {/* Enhanced Background Blob */}
          <motion.div
            animate={{
              scale: [1, 1.05, 1],
              rotate: [0, 5, -5, 0],
              opacity: [0.7, 0.85, 0.7]
            }}
            transition={{ duration: 10, repeat: Infinity, ease: "easeInOut", repeatType: "loop" }}
            whileHover={{
              scale: 1.1,
              opacity: 0.9,
              transition: { duration: 0.3 }
            }}
            whileTap={{
              scale: 0.95,
              transition: { duration: 0.1 }
            }}
            style={{
              position: 'absolute',
              top: '15%',
              left: '5%',
              width: 300,
              height: 300,
              background: 'radial-gradient(circle at 30% 30%, #4db6ac, #81c784 70%, transparent 100%)',
              borderRadius: '50%',
              filter: 'blur(60px)',
              opacity: 0.7,
              boxShadow: '0 0 40px rgba(77,182,172,0.3), 0 10px 30px rgba(129,199,132,0.2)',
              cursor: 'pointer'
            }}
          />

          {/* Floating Cube */}
          <motion.div
            animate={{ y: [0, -10, 0] }}
            transition={{ duration: 4, repeat: Infinity, ease: "easeInOut", loop: Infinity, repeatType: "loop" }}
            whileHover={{
              scale: 1.2,
              rotateX: 15,
              rotateY: 15,
              y: -15,
              boxShadow: '0 12px 30px rgba(77,182,172,0.6)',
              transition: { duration: 0.3 }
            }}
            whileTap={{
              scale: 0.9,
              rotateZ: 45,
              transition: { duration: 0.2 }
            }}
            style={{
              position: 'absolute',
              top: '30%',
              left: '55%',
              width: 80,
              height: 80,
              background: 'linear-gradient(135deg, #4db6ac 0%, #81c784 100%)',
              borderRadius: 8,
              boxShadow: '0 8px 20px rgba(77,182,172,0.4)',
              cursor: 'pointer',
              transformStyle: 'preserve-3d'
            }}
          />

          {/* 3D-like Shard */}
          <motion.div
            animate={{ rotate: [0, 15, -15, 0] }}
            transition={{ duration: 6, repeat: Infinity, ease: "easeInOut", loop: Infinity, repeatType: "loop" }}
            whileHover={{
              scale: 1.15,
              rotate: 30,
              y: -10,
              background: 'linear-gradient(180deg, #a5d6a7 0%, #26a69a 100%)',
              boxShadow: '0 8px 25px rgba(129,199,132,0.6)',
              transition: { duration: 0.4 }
            }}
            whileTap={{
              scale: 0.85,
              rotate: -30,
              transition: { duration: 0.15 }
            }}
            style={{
              position: 'absolute',
              top: '60%',
              left: '20%',
              width: 60,
              height: 120,
              background: 'linear-gradient(180deg, #81c784 0%, #4db6ac 100%)',
              borderRadius: 12,
              boxShadow: '0 4px 15px rgba(129,199,132,0.4)',
              cursor: 'pointer'
            }}
          />

          {/* Red Floating Sphere with Particles */}
          <Box sx={{ position: 'absolute', top: '50%', left: '75%', transform: 'translate(-50%, -50%)' }}>
            {/* The Main Sphere */}
            <motion.div
              animate={{ y: [0, 8, 0] }}
              transition={{ duration: 5, repeat: Infinity, ease: "easeInOut", loop: Infinity, repeatType: "loop" }}
              whileHover={{
                scale: 1.3,
                y: -12,
                background: 'radial-gradient(circle at 50% 50%, #ff6b6b, #e53935)',
                boxShadow: '0 8px 20px rgba(239,83,80,0.8), 0 0 30px rgba(239,83,80,0.4)',
                transition: { duration: 0.3 }
              }}
              whileTap={{
                scale: 0.8,
                transition: { duration: 0.1 }
              }}
              style={{
                width: 50,
                height: 50,
                background: 'radial-gradient(circle at 50% 50%, #ef5350, #c62828)',
                borderRadius: '50%',
                boxShadow: '0 4px 12px rgba(239,83,80,0.5)',
                cursor: 'pointer'
              }}
            />

            {/* Interactive Particle 1 */}
            <motion.div
              animate={{ x: [0, 5, 0], y: [0, -5, 0] }}
              transition={{ duration: 4, repeat: Infinity, ease: "easeInOut", repeatType: "loop", loop: Infinity }}
              whileHover={{
                scale: 2,
                x: 10,
                y: -10,
                backgroundColor: '#ffab91',
                boxShadow: '0 4px 12px rgba(255,171,145,0.7)',
                transition: { duration: 0.2 }
              }}
              whileTap={{
                scale: 0.5,
                transition: { duration: 0.1 }
              }}
              style={{
                position: 'absolute',
                top: -10,
                left: -10,
                width: 8,
                height: 8,
                backgroundColor: '#ff8a80',
                borderRadius: '50%',
                boxShadow: '0 2px 6px rgba(255,138,128,0.5)',
                cursor: 'pointer'
              }}
            />

            {/* Interactive Particle 2 */}
            <motion.div
              animate={{ x: [0, -4, 0], y: [0, 4, 0] }}
              transition={{ duration: 3.5, repeat: Infinity, ease: "easeInOut" }}
              whileHover={{
                scale: 1.8,
                x: -8,
                y: 8,
                backgroundColor: '#f8bbd9',
                boxShadow: '0 5px 15px rgba(248,187,217,0.6)',
                transition: { duration: 0.25 }
              }}
              whileTap={{
                scale: 0.3,
                transition: { duration: 0.1 }
              }}
              style={{
                position: 'absolute',
                bottom: -10,
                right: -10,
                width: 10,
                height: 10,
                backgroundColor: '#e57373',
                borderRadius: '50%',
                boxShadow: '0 3px 8px rgba(229,115,115,0.4)',
                cursor: 'pointer'
              }}
            />

            {/* Interactive Particle 3 */}
            <motion.div
              animate={{
                x: [0, 3, 0],
                y: [0, -3, 0]
              }}
              transition={{
                duration: 4.5,
                repeat: Infinity,
                ease: "easeInOut",
                repeatType: "loop"
              }}
              whileHover={{
                scale: 2,
                x: 4,
                y: -4,
                backgroundColor: '#ff7043',
                boxShadow: '0 2px 8px rgba(255,112,67,0.6)',
                transition: { duration: 0.9, ease: "easeOut" }
              }}
              whileTap={{
                scale: 0.5,
                rotate: 90,
                transition: { duration: 0.15 }
              }}
              style={{
                position: 'absolute',
                top: 5,
                right: -8,
                width: 6,
                height: 6,
                backgroundColor: '#ff5252',
                borderRadius: '50%',
                boxShadow: '0 2px 5px rgba(255,82,82,0.3)',
                cursor: 'pointer'
              }}
            />
          </Box>

        </Box>
      </Box>
    </Box>
  )
}